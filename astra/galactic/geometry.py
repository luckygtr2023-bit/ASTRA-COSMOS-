"""Reduced-order spatial helpers."""
from __future__ import annotations

import math
from typing import Tuple

from .errors import GalacticNumericalError
from .types import Vec3, CoordinateContext, DistanceKind


def comoving_separation_mpc(a: Vec3, b: Vec3) -> float:
    """Comoving separation (no expansion)."""
    if not isinstance(a, Vec3) or not isinstance(b, Vec3):
        raise GalacticNumericalError("positions must be Vec3")
    return (a - b).norm()


def proper_separation_mpc(a: Vec3, b: Vec3, scale_factor: float) -> float:
    """Proper separation = a(t) * comoving separation."""
    if scale_factor <= 0.0 or not math.isfinite(scale_factor):
        raise GalacticNumericalError("scale_factor must be finite > 0")
    return comoving_separation_mpc(a, b) * scale_factor


def separation_by_kind(
    a: Vec3,
    b: Vec3,
    ctx: CoordinateContext,
    kind: DistanceKind,
) -> float:
    """Distance declaring its CoordinateContext + DistanceKind."""
    if not isinstance(ctx, CoordinateContext):
        raise GalacticNumericalError("ctx must be CoordinateContext")
    if not isinstance(kind, DistanceKind):
        raise GalacticNumericalError("kind must be DistanceKind")
    comoving = comoving_separation_mpc(a, b)
    if kind == DistanceKind.COMOVING:
        return comoving
    if kind == DistanceKind.PROPER:
        return comoving * ctx.scale_factor
    if kind == DistanceKind.REDSHIFT_DERIVED:
        # redshift-derived approximates comoving in low-z; outside low-z caller
        # should use cosmology provider
        return comoving
    if kind in (DistanceKind.LUMINOSITY, DistanceKind.ANGULAR_DIAMETER):
        # Without full cosmology these are approximations; document limitation
        return comoving * ctx.scale_factor
    return comoving


def virial_radius_from_mass(mass_kg: float, overdensity: float = 200.0) -> float:
    """Approximate R_vir ~ (3M / (4π · Δ · ρ_c))^(1/3). RHO_C is a constant."""
    RHO_C_KG_M3 = 8.6e-27  # critical density, approximate
    if not isinstance(mass_kg, (int, float)) or isinstance(mass_kg, bool):
        raise GalacticNumericalError("mass must be numeric")
    if mass_kg <= 0.0 or not math.isfinite(float(mass_kg)):
        raise GalacticNumericalError("mass must be finite > 0")
    if not isinstance(overdensity, (int, float)) or isinstance(overdensity, bool):
        raise GalacticNumericalError("overdensity must be numeric")
    if overdensity <= 0.0 or not math.isfinite(float(overdensity)):
        raise GalacticNumericalError("overdensity must be finite > 0")
    volume = (3.0 * float(mass_kg)) / (4.0 * math.pi * float(overdensity) * RHO_C_KG_M3)
    r_m = volume ** (1.0 / 3.0)
    return r_m / 3.085677581491367e22  # meters -> Mpc


def center_of_mass(positions: Tuple[Vec3, ...], masses: Tuple[float, ...]) -> Vec3:
    """Mass-weighted center, deterministic (ordered inputs)."""
    if len(positions) != len(masses):
        raise GalacticNumericalError("positions and masses length mismatch")
    if not positions:
        raise GalacticNumericalError("need at least one position")
    tot = 0.0
    sx = sy = sz = 0.0
    for p, m in zip(positions, masses):
        if not isinstance(p, Vec3):
            raise GalacticNumericalError("positions must be Vec3")
        fv = float(m)
        if not math.isfinite(fv) or fv <= 0:
            raise GalacticNumericalError(f"mass must be finite >0, got {m!r}")
        tot += fv
        sx += p.x * fv
        sy += p.y * fv
        sz += p.z * fv
    if tot == 0:
        raise GalacticNumericalError("total mass zero")
    return Vec3(sx / tot, sy / tot, sz / tot)
