"""Deterministic fragmentation.

Given an impact's energy budget and the target's damage state, produce N
fragments with a deterministic mass distribution, positions, and velocities.

Determinism contract
--------------------
- All randomness comes from an injected ``astra.core.rng.RNGStream`` (or any
  object satisfying the RNGProvider protocol: ``next_float() -> float``).
- Same RNG stream state + same ImpactEvent + same config => identical
  fragment tuple. Callers that want per-impact reproducibility inject a
  freshly seeded stream (see ``make_impact_rng``); callers that want a
  continuous replayable sequence inject a long-lived stream owned by a core
  ``DeterministicRNG`` whose state participates in core snapshots.
- No global RNG. No wall-clock. No ID-hash-derived physics.

Conservation
------------
- Mass:  sum(fragment masses) <= target mass, exactly by construction
  (Dirichlet weights normalised to 1, fragments below the mass floor are
  dropped, which can only REDUCE the total).
- Momentum: fragment velocity perturbations are mean-subtracted with the
  same weights as the mass distribution, so sum(m_i * dv_i) == 0 up to
  float round-off: the fragment cloud preserves the target's centre-of-mass
  momentum.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Protocol, Tuple

from astra.core.rng import DeterministicRNG, RNGStream

from .config import DestructionConfig
from .damage import DamageState
from .errors import LimitExceededError, NumericalError
from .provenance import DataProvenance
from .types import FragmentState, ImpactEnergy, ImpactEvent
from astra.mathematics import Vector3


class RNGProvider(Protocol):
    """Minimal deterministic RNG surface used by this package.

    Satisfied structurally by ``astra.core.rng.RNGStream``.
    """

    def next_float(self) -> float:
        """Uniform float in [0, 1)."""
        ...


def make_impact_rng(seed: int, stream_name: str) -> RNGStream:
    """Create a fresh, core-backed deterministic RNG stream for one impact.

    Uses astra.core.rng.DeterministicRNG so the stream is a first-class
    replayable core RNG (get_state/restore_state), not a local ad-hoc PRNG.
    """
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise NumericalError("seed must be an int")
    manager = DeterministicRNG(global_seed=seed)
    return manager.create_stream(name=f"{stream_name}.{seed}", seed=seed)


@dataclass(frozen=True)
class FragmentationInput:
    event: ImpactEvent
    energy: ImpactEnergy
    target_state: DamageState
    seed: int
    target_radius_m: float


def _determine_fragment_count(inp: FragmentationInput, config: DestructionConfig) -> int:
    """Deterministic fragment count: bounded log scaling of fragmentation energy.

    The fragmentation model always yields at least 2 fragments (a single
    fragment is not a fragmentation). A configured cap below 2 is therefore
    a configuration contradiction and raises LimitExceededError when
    fragmentation is actually required.
    """
    cap = config.limits.max_fragments_per_impact
    if cap < 2:
        raise LimitExceededError(
            f"fragmentation of a fractured body requires >= 2 fragments; "
            f"limits.max_fragments_per_impact is {cap}"
        )
    e_ref = 1.0e6  # reference energy scale (J), model parameter
    ratio = inp.energy.fragmentation_energy_j / e_ref
    raw = int(round(math.log1p(max(0.0, ratio)) * 4.0)) + 2
    return min(cap, max(2, raw))


def fragment_target(
    inp: FragmentationInput,
    config: DestructionConfig,
    rng: RNGProvider,
) -> Tuple[FragmentState, ...]:
    """Produce deterministic fragments of the target body."""
    if inp.target_state not in (
        DamageState.FRACTURED,
        DamageState.FRAGMENTED,
        DamageState.DESTROYED,
    ):
        raise NumericalError("fragmentation called on non-fractured target")

    m_total = inp.event.target_mass_kg
    if m_total <= 0.0:
        raise NumericalError("target mass must be positive")

    n = _determine_fragment_count(inp, config)

    # Deterministic mass distribution: Dirichlet(1,...,1) via normalized
    # exponentials (-log(u) is Exp(1) for u uniform on (0,1]).
    weights: List[float] = []
    for _ in range(n):
        u = rng.next_float()
        if u <= 0.0:
            u = 1.0 / float(1 << 53)
        weights.append(-math.log(u))
    w_sum = sum(weights)
    if w_sum <= 0.0:
        # Degenerate; fall back to uniform masses (deterministic).
        weights = [1.0] * n
        w_sum = float(n)

    # Characteristic ejection speed scale from the fragmentation energy.
    speed_scale = max(
        1e-9, 2.0 * inp.energy.fragmentation_energy_j / max(m_total, 1e-30)
    )
    speed_scale = math.sqrt(speed_scale)  # m/s

    # Raw isotropic directions from the RNG.
    raw_dirs: List[Vector3] = []
    for _ in range(n):
        x = rng.next_float() * 2.0 - 1.0
        y = rng.next_float() * 2.0 - 1.0
        z = rng.next_float() * 2.0 - 1.0
        v = Vector3(x, y, z)
        if v.magnitude() == 0.0:
            v = Vector3(1.0, 0.0, 0.0)
        try:
            raw_dirs.append(v.normalized())
        except ZeroDivisionError as exc:  # pragma: no cover - defensive
            raise NumericalError("cannot normalize fragment direction") from exc

    # Weighted mean direction; subtracting it zeroes net perturbation
    # momentum because fragment masses are proportional to the same weights.
    mean_dir = Vector3(0.0, 0.0, 0.0)
    for w, d in zip(weights, raw_dirs):
        mean_dir = mean_dir + d * w
    mean_dir = mean_dir / w_sum
    dirs = [d - mean_dir for d in raw_dirs]

    cm_v = inp.event.target_velocity
    fragments: List[FragmentState] = []
    for i in range(n):
        m_i = m_total * (weights[i] / w_sum)
        if m_i < config.limits.min_fragment_mass_kg:
            continue
        # Deterministic radial offset scaled to target radius.
        r = inp.target_radius_m * (0.5 + 0.5 * (i + 0.5) / n)
        pos = inp.event.target_position + raw_dirs[i] * r
        vel = cm_v + dirs[i] * speed_scale
        fragments.append(
            FragmentState(
                fragment_id=f"{inp.event.target_id}:frag:{i}",
                parent_id=inp.event.target_id,
                impact_id=inp.event.impact_id,
                mass_kg=m_i,
                position=pos,
                velocity=vel,
                created_at_s=inp.event.sim_time_s,
                provenance=DataProvenance.SIMULATED_DATA,
            )
        )

    if len(fragments) > config.limits.max_fragments_per_impact:
        raise LimitExceededError(
            f"fragment count {len(fragments)} exceeds limit "
            f"{config.limits.max_fragments_per_impact}"
        )
    return tuple(fragments)
