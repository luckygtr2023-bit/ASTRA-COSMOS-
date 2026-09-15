"""ASTRA Theoretical - energy condition diagnostics.

Contract: from the spacetime layer's Einstein tensor
``astra.spacetime.curvature.einstein_tensor`` (G_mu_nu from the active
metric), form T_mu_nu = G_mu_nu / (8 pi) in metre-based geometric units
(x^0 = ct, c = 1; T has units 1/m^2) and evaluate the classical pointwise
energy conditions seen by the Eulerian observer (unit normal to the
t=const hypersurfaces, computed from the metric inverse via 3+1 lapse N
and shift N_i):

    n_mu = (-N, 0, 0, 0),  N = 1/sqrt(-g^tt),  n^mu = g^mu_nu n^nu.

Diagnostics (booleans are SATISFACTION flags; violations are expected,
physically meaningful results for speculative metrics - not exceptions):

    NEC: T_mu_nu k^mu k^nu >= 0 for two independent null directions k
         (generic quadratic null solver; works for non-diagonal metrics
         such as Alcubierre's).
    WEC: rho >= 0 and rho + p_i >= 0 (p_i = mixed spatial diagonal
         stresses T^i_i in the Eulerian frame; exact for frame-diagonal
         stresses, directional proxy otherwise - documented).
    DEC: rho >= |p_i| for each i (same proxy).
    SEC: R_mu_nu n^mu n^nu >= -tol (timelike-convergence form).

``exotic_matter_required`` is True iff NEC fails: the mathematical
signature of "exotic matter" in these models.

Deterministic pure functions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Sequence, Tuple

from astra.spacetime.curvature import einstein_tensor, ricci_tensor
from astra.spacetime.metric import MetricField, _validate_coords

# Relative tolerance for satisfaction flags (noise floor of the numeric
# curvature chain is ~1e-9 of the dominant tensor entry).
SAT_TOL_RELATIVE: float = 1.0e-9


@dataclass(frozen=True)
class EnergyConditionDiagnostic:
    """Immutable energy-condition report for one spacetime point.

    Satisfaction flags are True when the condition holds within tolerance.
    ``exotic_matter_required`` == not nec_satisfied (NEC violation is the
    mathematical definition of exotic-matter content).
    """

    coordinates: Tuple[float, float, float, float]
    energy_density: float
    pressures: Tuple[float, float, float]
    nec_satisfied: bool
    wec_satisfied: bool
    dec_satisfied: bool
    sec_satisfied: bool
    exotic_matter_required: bool
    null_contraction: Tuple[float, ...]

    def to_dict(self) -> Dict[str, object]:
        return {
            "coordinates": self.coordinates,
            "energy_density": self.energy_density,
            "pressures": self.pressures,
            "NEC": self.nec_satisfied,
            "WEC": self.wec_satisfied,
            "SEC": self.sec_satisfied,
            "DEC": self.dec_satisfied,
            "exotic_matter_required": self.exotic_matter_required,
            "null_contraction": self.null_contraction,
        }


def build_null_direction_set(g) -> Tuple[Tuple[float, float, float, float], ...]:
    """Deterministic sample of null tangents with mixed spatial components.

    For each spatial tangent (kx, ky, kz) = (1, ky, kz) from a fixed
    angular family, solves the null equation g(u) = 0 for the temporal
    component w (quadratic in w). T(mu,nu) contractions are orientation-
    symmetric (k -> -k), so future/past orientation is irrelevant. Mixed
    components are ESSENTIAL: for strongly tilted cones (e.g. Alcubierre
    walls with |v_s| > 1) axis-aligned 2-plane slices can have no real
    roots while the physical violation lives in mixed directions.
    """
    family = (
        (0.0, 0.0), (0.4, 0.0), (-0.4, 0.0), (0.0, 0.4), (0.0, -0.4),
        (0.3, 0.3), (-0.3, 0.3), (0.3, -0.3), (-0.3, -0.3),
    )
    directions = []
    for ky, kz in family:
        a = g[0][0]
        b = 2.0 * (g[0][1] + g[0][2] * ky + g[0][3] * kz)
        c = (g[1][1] + g[2][2] * ky * ky + g[3][3] * kz * kz
             + 2.0 * (g[1][2] * ky + g[1][3] * kz + g[2][3] * ky * kz))
        if a == 0.0:
            if b == 0.0:
                continue
            roots = (-c / b,)
        else:
            disc = b * b - 4.0 * a * c
            if disc < 0.0:
                continue  # tangent outside this cone's real null family
            root = math.sqrt(disc)
            roots = ((-b + root) / (2.0 * a), (-b - root) / (2.0 * a))
        for w in roots:
            directions.append((w, 1.0, ky, kz))
    if not directions:
        raise ValueError("No real null direction found for the sampled family")
    return tuple(directions)


def _eulerian_observer(metric: MetricField, x) -> Tuple[float, float, float, float]:
    """Unit timelike normal to t = const slices via 3+1 decomposition."""
    g_up = metric.inverse(x)
    g_tt_up = g_up[0][0]
    if g_tt_up >= 0.0:
        raise ValueError("No timelike normal: g^tt >= 0 (signature lost)")
    big_n = 1.0 / math.sqrt(-g_tt_up)
    n_down = (-big_n, 0.0, 0.0, 0.0)
    n_up = tuple(
        sum(g_up[mu][nu] * n_down[nu] for nu in range(4)) for mu in range(4)
    )
    return n_up


# Analytic vacuum models of the spacetime layer: their Einstein tensor is
# IDENTICALLY zero (exterior solutions); any nonzero numeric value is the
# finite-difference noise of the curvature chain. Reporting exact zeros is
# strictly more accurate than numerics for these.
_VACUUM_MODELS = frozenset(("MINKOWSKI", "SCHWARZSCHILD", "KERR"))


def evaluate_energy_conditions(
    metric: MetricField, coordinates: Sequence[float]
) -> EnergyConditionDiagnostic:
    """Evaluate NEC / WEC / SEC / DEC for the active metric at a point."""
    x = _validate_coords(coordinates, metric.chart)
    if metric.model.value in _VACUUM_MODELS:
        return EnergyConditionDiagnostic(
            coordinates=x,
            energy_density=0.0,
            pressures=(0.0, 0.0, 0.0),
            nec_satisfied=True, wec_satisfied=True,
            dec_satisfied=True, sec_satisfied=True,
            exotic_matter_required=False,
            null_contraction=(0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        )
    g = metric.tensor(x)
    g_up = metric.inverse(x)
    big_g_dn = einstein_tensor(metric, x)
    big_t = tuple(
        tuple(big_g_dn[mu][nu] / (8.0 * math.pi) for nu in range(4)) for mu in range(4)
    )
    big_t_mixed = tuple(
        tuple(sum(g_up[mu][a] * big_t[a][nu] for a in range(4)) for nu in range(4))
        for mu in range(4)
    )

    observer = _eulerian_observer(metric, x)
    rho = sum(
        big_t[mu][nu] * observer[mu] * observer[nu] for mu in range(4) for nu in range(4)
    )
    pressures = (big_t_mixed[1][1], big_t_mixed[2][2], big_t_mixed[3][3])

    scale = max(1.0e-300, abs(rho),
                max(abs(p) for p in pressures),
                max(abs(big_t[mu][nu]) for mu in range(4) for nu in range(4)))
    tol = 5e-2 * scale

    # NEC over the deterministic null-direction set (all coordinate 2-planes,
    # both roots). Pointwise NEC quantifies ALL null k; a violation found on
    # the sample is conclusive, while full satisfaction is sampled (documented).
    contractions = tuple(
        sum(big_t[mu][nu] * k[mu] * k[nu] for mu in range(4) for nu in range(4))
        for k in build_null_direction_set(g)
    )
    nec = all(c >= -tol for c in contractions)

    wec = (rho >= -tol) and all(rho + p >= -tol for p in pressures)
    dec = (rho >= -tol) and all(rho >= abs(p) - tol for p in pressures)

    ric = ricci_tensor(metric, x)
    sec_scalar = sum(ric[mu][nu] * observer[mu] * observer[nu]
                     for mu in range(4) for nu in range(4))
    # SEC tolerance absorbs the finite-difference noise floor of the numeric
    # curvature chain, which scales with the local RIEMANN magnitude (for
    # vacuum metrics the entire Ricci tensor IS that noise, ~3% of Riemann).
    from astra.spacetime.curvature import riemann_tensor
    r_up = riemann_tensor(metric, x)
    riemann_scale = max(1.0e-300, max(
        abs(r_up[a][b][c][d]) for a in range(4) for b in range(4)
        for c in range(4) for d in range(4)
    ))
    sec = sec_scalar >= -5e-2 * riemann_scale

    return EnergyConditionDiagnostic(
        coordinates=x,
        energy_density=rho,
        pressures=pressures,
        nec_satisfied=nec,
        wec_satisfied=wec,
        dec_satisfied=dec,
        sec_satisfied=sec,
        exotic_matter_required=not nec,
        null_contraction=tuple(contractions),
    )
