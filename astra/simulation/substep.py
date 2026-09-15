"""Safe substepping — separates simulation rate from numerical timestep.

Requested elapsed simulation time → scheduler → safe numerical substeps → system updates.

If Δt > max_step, subdivides deterministically (no hidden rate change)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List

from .exceptions import InvalidTimestepError, LargeJumpRejectedError


@dataclass(frozen=True)
class SubstepPolicy:
    """Policy for safe substepping."""

    max_step_s: float = 3600.0  # default 1 hour safe for physics
    min_step_s: float = 1e-9
    max_substeps: int = 1_000_000  # beyond this, reject
    allow_analytical: bool = False  # if True, large jumps may use analytical propagator hook

    def validate(self) -> None:
        if not math.isfinite(self.max_step_s) or self.max_step_s <= 0:
            raise InvalidTimestepError(f"max_step_s must be finite >0, got {self.max_step_s!r}")
        if not math.isfinite(self.min_step_s) or self.min_step_s <= 0:
            raise InvalidTimestepError(f"min_step_s must be finite >0, got {self.min_step_s!r}")
        if self.min_step_s > self.max_step_s:
            raise InvalidTimestepError("min_step_s cannot exceed max_step_s")
        if self.max_substeps <= 0:
            raise InvalidTimestepError("max_substeps must be >0")


def validate_dt(dt: float, name: str = "dt") -> float:
    if isinstance(dt, bool) or not isinstance(dt, (int, float)):
        raise InvalidTimestepError(f"{name} must be a number, got {type(dt).__name__}")
    v = float(dt)
    if math.isnan(v) or math.isinf(v):
        raise InvalidTimestepError(f"{name} cannot be NaN/Inf, got {dt!r}")
    if v < 0.0:
        raise InvalidTimestepError(f"{name} cannot be negative, got {v!r}")
    if v == 0.0:
        return 0.0
    if v > 1e18:
        raise InvalidTimestepError(f"{name} overflow beyond 1e18s, got {v!r}")
    if v < 1e-12 and v != 0.0:
        # extremely small but allow; caller must decide
        pass
    return v


def validate_rate(rate: float) -> float:
    from .exceptions import InvalidRateError
    if isinstance(rate, bool) or not isinstance(rate, (int, float)):
        raise InvalidRateError(f"rate must be a number, got {type(rate).__name__}")
    v = float(rate)
    if math.isnan(v) or math.isinf(v):
        raise InvalidRateError(f"rate cannot be NaN/Inf, got {rate!r}")
    if v <= 0.0:
        raise InvalidRateError(f"rate must be >0, got {v!r}")
    if v > 1e12:
        raise InvalidRateError(f"rate exceeds supported 1e12, got {v!r}")
    if v < 1e-12:
        raise InvalidRateError(f"rate below supported 1e-12, got {v!r}")
    return v


def subdivide(delta_s: float, policy: SubstepPolicy) -> List[float]:
    """Subdivide requested delta into safe substeps deterministically.

    Returns list of steps summing to delta_s within floating error < 1e-12.
    Deterministic: same delta + same policy → same list.
    """
    policy.validate()
    delta = validate_dt(delta_s, "delta_s")
    if delta == 0.0:
        return []
    if delta < policy.min_step_s:
        # Single tiny step (explicit)
        return [delta]
    n_full = int(delta // policy.max_step_s)
    remainder = delta - n_full * policy.max_step_s
    # Correct for floating error: if remainder very small, fold
    if remainder < 1e-12 and n_full > 0:
        remainder = 0.0
    # Check budget
    n_total = n_full + (1 if remainder > 1e-12 else 0)
    if n_total > policy.max_substeps:
        if policy.allow_analytical:
            # Caller may use analytical hook; we still return subdivided capped
            # but signal via exception? For now we raise and caller may handle
            raise LargeJumpRejectedError(
                f"requested {delta_s} requires {n_total} substeps > budget {policy.max_substeps}; use analytical propagator or increase max_step",
                details={"delta": delta_s, "required": n_total, "budget": policy.max_substeps},
            )
        raise LargeJumpRejectedError(
            f"requested {delta_s} requires {n_total} substeps > budget {policy.max_substeps}",
            details={"delta": delta_s, "required": n_total, "budget": policy.max_substeps},
        )
    steps: List[float] = []
    for _ in range(n_full):
        steps.append(policy.max_step_s)
    if remainder > 1e-12:
        # Use remainder as final step (may be < max_step)
        # To avoid tiny remainder, we could distribute remainder across steps, but deterministic simpler: append
        steps.append(remainder)
    # Verify sum
    # Due to binary floating, we accept tiny error
    if steps and abs(sum(steps) - delta) > 1e-9:
        # Adjust last step to exactly match delta
        err = delta - sum(steps)
        steps[-1] += err
    return steps


def apply_rate(delta_real_s: float, rate: float, policy: SubstepPolicy) -> List[float]:
    """Apply simulation rate to real delta, then subdivide.

    Separate simulation rate from numerical step.
    """
    dr = validate_dt(delta_real_s, "delta_real_s")
    r = validate_rate(rate)
    delta_sim = dr * r
    # Overflow check after multiplication
    if not math.isfinite(delta_sim):
        raise InvalidTimestepError(f"delta_sim overflow: {dr}*{r} -> {delta_sim!r}")
    if delta_sim > 1e18:
        raise InvalidTimestepError(f"delta_sim overflow beyond 1e18s: {delta_sim!r}")
    return subdivide(delta_sim, policy)
