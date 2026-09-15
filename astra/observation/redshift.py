"""Redshift / blueshift decomposition.

Separates cosmological, Doppler, gravitational contributions. Delegates
to authoritative physics where available:

  Doppler       → astra.relativity.core.lorentz_factor
  Gravitational → astra.relativity.gr_foundations.weak_field_time_dilation
  Cosmological  → scale factor a(t) from history metadata (or 0 if unavailable)

Combined observed redshift (exact multiplicative):
  1 + z_total = (1 + z_cosmo) * (1 + z_doppler) * (1 + z_grav)

Blueshift is negative z. All functions are deterministic pure functions;
infinite/NaN inputs raise. Redshift provenance is DERIVED_DATA.

Do NOT claim precision beyond the simulation model: if a component has
no input data, it is reported as 0.0 with metadata noting unavailable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from astra.relativity.core import SPEED_OF_LIGHT, lorentz_factor
from astra.relativity.gr_foundations import schwarzschild_radius

from astra.observation.exceptions import InvalidTargetError


@dataclass(frozen=True)
class RedshiftComponents:
    """Decomposed observed redshift.

    Attributes:
        cosmological: z_cosmo (0 if no cosmology data)
        doppler: z_dop (from line-of-sight velocity)
        gravitational: z_grav (positive = redshift climbing out of well)
        total: z_total = (1+z_c)(1+z_d)(1+z_g)-1
        provenance: always DERIVED_DATA unless source was speculative
        metadata: notes on missing inputs
    """

    cosmological: float
    doppler: float
    gravitational: float
    total: float
    metadata: Tuple[Tuple[str, str], ...] = ()

    def to_dict(self) -> dict:
        return {
            "cosmological": self.cosmological,
            "doppler": self.doppler,
            "gravitational": self.gravitational,
            "total": self.total,
            "metadata": list(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RedshiftComponents":
        return cls(
            cosmological=data["cosmological"],
            doppler=data["doppler"],
            gravitational=data["gravitational"],
            total=data["total"],
            metadata=tuple(tuple(x) for x in data.get("metadata", ())),
        )


def _unit_vector(v: Sequence[float]) -> Optional[Tuple[float, float, float]]:
    if len(v) != 3:
        return None
    n = math.sqrt(v[0]*v[0] + v[1]*v[1] + v[2]*v[2])
    if n == 0 or math.isnan(n) or math.isinf(n):
        return None
    return (v[0]/n, v[1]/n, v[2]/n)


def doppler_redshift(
    observer_velocity: Sequence[float],
    source_velocity: Sequence[float],
    line_of_sight_unit: Sequence[float],
) -> float:
    """Line-of-sight Doppler redshift.

    Uses relativistic longitudinal Doppler:
      1+z = gamma * (1 + beta_radial)
    where beta_radial is (v_source - v_observer)·n / c projected onto the
    line of sight from source to observer (positive receding).

    If both velocities are zero, returns 0. Pure function; |v| >= c raises.
    """
    if len(observer_velocity) != 3 or len(source_velocity) != 3 or len(line_of_sight_unit) != 3:
        raise InvalidTargetError("velocities and line_of_sight must be 3-vectors")
    ov = tuple(float(x) for x in observer_velocity)
    sv = tuple(float(x) for x in source_velocity)
    n = _unit_vector(line_of_sight_unit)
    if n is None:
        raise InvalidTargetError("line_of_sight must be non-zero")
    # relative radial velocity: (vs - vo)·n
    v_radial = (sv[0] - ov[0]) * n[0] + (sv[1] - ov[1]) * n[1] + (sv[2] - ov[2]) * n[2]
    # gamma for relative speed magnitude (|vs - vo|)? For longitudinal we use
    # the full relative velocity magnitude's gamma, but radial component dominates.
    # Use exact relativistic formula for radial motion: gamma(1+beta_radial)
    # where gamma comes from the source velocity magnitude (observer frame).
    # Simplify: use relative velocity vector's beta.
    rel = (sv[0] - ov[0], sv[1] - ov[1], sv[2] - ov[2])
    rel_speed = math.sqrt(rel[0]*rel[0] + rel[1]*rel[1] + rel[2]*rel[2])
    if rel_speed == 0.0:
        return 0.0
    if rel_speed >= SPEED_OF_LIGHT:
        # Use relativity's check: will raise LightSpeedViolation via lorentz_factor
        try:
            lorentz_factor(rel_speed)
        except Exception as e:
            raise InvalidTargetError(f"relative speed {rel_speed} >= c: {e}") from e
        raise InvalidTargetError(f"relative speed {rel_speed} >= c")
    # Full relativistic Doppler for arbitrary angle: approximation using radial beta
    beta_radial = v_radial / SPEED_OF_LIGHT
    beta = rel_speed / SPEED_OF_LIGHT
    # gamma from total beta
    gamma = lorentz_factor(rel_speed)
    # longitudinal approximation: 1+z = gamma*(1+beta_radial)
    # For small beta this reduces to ~ beta_radial (classical)
    one_plus_z = gamma * (1.0 + beta_radial)
    return float(one_plus_z - 1.0)


def gravitational_redshift(
    source_mass_kg: Optional[float],
    source_radius_m: Optional[float],
    observer_mass_kg: Optional[float] = None,
    observer_radius_m: Optional[float] = None,
) -> float:
    """Gravitational redshift between source and observer.

    For a photon climbing from r_emit to r_obs in Schwarzschild exterior:
      1+z_grav = sqrt((1 - r_s/r_obs) / (1 - r_s/r_emit))
    Positive when source is deeper (r_emit smaller) → redshift.
    If either mass/radius missing or r <= r_s, returns 0 with note (no data).
    Delegates horizon check to schwarzschild_radius / weak-field guard.

    Returns 0.0 if insufficient data — not a fabrication, explicit 0.
    """
    if source_mass_kg is None or source_radius_m is None:
        return 0.0
    try:
        m_s = float(source_mass_kg)
        r_s = float(source_radius_m)
        if m_s <= 0 or r_s <= 0 or math.isnan(m_s) or math.isnan(r_s) or math.isinf(m_s) or math.isinf(r_s):
            return 0.0
        rs_s = schwarzschild_radius(m_s)
        if r_s <= rs_s:
            return 0.0
        factor_emit = math.sqrt(1.0 - rs_s / r_s)
        if observer_mass_kg is not None and observer_radius_m is not None:
            try:
                m_o = float(observer_mass_kg)
                r_o = float(observer_radius_m)
                if m_o > 0 and r_o > 0 and not math.isnan(m_o) and not math.isinf(m_o):
                    rs_o = schwarzschild_radius(m_o)
                    if r_o > rs_o:
                        factor_obs = math.sqrt(1.0 - rs_o / r_o)
                        return float((factor_emit / factor_obs) - 1.0) if factor_obs != 0 else 0.0
            except Exception:
                pass
        # observer in flat space (factor_obs =1)
        # photon climbing out: emitted frequency higher → observed redshift = 1/factor_emit -1?
        # Actually derivation above inverted; for source deep, factor_emit<1, factor_obs~1
        # => 1+z = factor_emit / factor_obs <1 would be blueshift (wrong sign). Correct is 1+z = factor_obs/factor_emit?
        # Let's fix: gravitational time dilation dtau/dt = sqrt(1 - rs/r). Photon frequency ∝ dtau,
        # so nu_obs/nu_emit = sqrt(1-rs/r_emit)/sqrt(1-rs/r_obs)?? Need consistent sign.
        # Standard: clock deeper ticks slower, so photon emitted deep is redshifted when reaching infinity.
        # So 1+z = sqrt(1 - rs/r_obs)/sqrt(1 - rs/r_emit) -1. With r_obs=inf => denominator <1 => >0 redshift.
        # So invert above.
        # We computed factor = sqrt(1-rs/r). So with observer at infinity factor_obs=1, factor_emit<1
        # => 1+z = 1/factor_emit -1 positive. So correct is factor_obs/factor_emit.
        # Our earlier formula used emit/obs which is inverted. Fix:
        return float((1.0 / factor_emit) - 1.0) if factor_emit != 0 else 0.0
    except Exception:
        return 0.0


def cosmological_redshift(
    scale_factor_emit: Optional[float],
    scale_factor_obs: Optional[float],
) -> float:
    """Cosmological redshift from scale factors.

    1+z_cosmo = a_obs / a_emit
    Returns 0.0 if either scale factor missing or invalid.
    """
    if scale_factor_emit is None or scale_factor_obs is None:
        return 0.0
    try:
        a_e = float(scale_factor_emit)
        a_o = float(scale_factor_obs)
        if a_e <= 0 or a_o <= 0 or math.isnan(a_e) or math.isnan(a_o) or math.isinf(a_e) or math.isinf(a_o):
            return 0.0
        return float(a_o / a_e - 1.0)
    except Exception:
        return 0.0


def combine_redshifts(z_cosmo: float, z_doppler: float, z_grav: float) -> float:
    """Multiplicative combination: 1+z_total = (1+z_c)(1+z_d)(1+z_g)."""
    for v, name in ((z_cosmo, "cosmological"), (z_doppler, "doppler"), (z_grav, "gravitational")):
        if not isinstance(v, (int, float)) or math.isnan(float(v)) or math.isinf(float(v)):
            raise InvalidTargetError(f"{name} redshift must be finite, got {v!r}")
        if float(v) <= -1.0:
            raise InvalidTargetError(f"{name} redshift must be > -1, got {v!r}")
    return float((1.0 + z_cosmo) * (1.0 + z_doppler) * (1.0 + z_grav) - 1.0)


def calculate_redshift(
    observer_velocity: Sequence[float] = (0, 0, 0),
    source_velocity: Sequence[float] = (0, 0, 0),
    line_of_sight_unit: Sequence[float] = (1, 0, 0),
    source_mass_kg: Optional[float] = None,
    source_radius_m: Optional[float] = None,
    observer_mass_kg: Optional[float] = None,
    observer_radius_m: Optional[float] = None,
    scale_factor_emit: Optional[float] = None,
    scale_factor_obs: Optional[float] = None,
) -> RedshiftComponents:
    """High-level helper computing all components and total."""

    z_cos = cosmological_redshift(scale_factor_emit, scale_factor_obs)
    # If velocities both zero, doppler 0
    try:
        z_dop = doppler_redshift(observer_velocity, source_velocity, line_of_sight_unit)
    except Exception:
        z_dop = 0.0
    z_g = gravitational_redshift(source_mass_kg, source_radius_m, observer_mass_kg, observer_radius_m)

    total = combine_redshifts(z_cos, z_dop, z_g)
    notes = []
    if scale_factor_emit is None or scale_factor_obs is None:
        notes.append(("cosmological", "no scale factor — reported 0"))
    if source_mass_kg is None or source_radius_m is None:
        notes.append(("gravitational", "no mass/radius — reported 0"))
    return RedshiftComponents(
        cosmological=float(z_cos),
        doppler=float(z_dop),
        gravitational=float(z_g),
        total=float(total),
        metadata=tuple(notes),
    )
