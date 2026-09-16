"""Classical orbital elements and state <-> elements conversion.

Elements follow the standard 3-1-3 Euler sequence:
    R_z(omega) . R_x(i) . R_z(Omega) : inertial -> perifocal

Semi-latus rectum p is used as the primary geometric parameter so that
parabolic orbits (e = 1) can be represented without special-casing.

Degenerate cases
----------------
- Circular (e < CIRCULAR_TOL): argument_of_periapsis is undefined; we set
  it to 0.0 and set the `is_circular` flag.
- Equatorial (i < EQUATORIAL_TOL or |i - pi| < EQUATORIAL_TOL): RAAN is
  undefined; we set raan to 0.0 and set the `is_equatorial` flag.
- Parabolic (|e - 1| < PARABOLIC_TOL): semi_major_axis is +inf; use
  semi_latus_rectum directly.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict
import math

from astra.mathematics import Vector3, Matrix3
from astra.orbital.constants import (
    CIRCULAR_TOL, EQUATORIAL_TOL, PARABOLIC_TOL, NODE_TOL,
)
from astra.orbital.errors import (
    DegenerateOrbitError, InvalidOrbitError,
)
from astra.orbital.state import OrbitalState


@dataclass(frozen=True)
class ClassicalOrbitalElements:
    semi_latus_rectum: float
    eccentricity: float
    inclination: float
    raan: float
    argument_of_periapsis: float
    true_anomaly: float
    mu: float
    is_circular: bool = False
    is_equatorial: bool = False
    is_parabolic: bool = False

    def __post_init__(self):
        if not (math.isfinite(self.semi_latus_rectum) and self.semi_latus_rectum > 0.0):
            raise InvalidOrbitError(
                f"semi_latus_rectum must be positive finite, got {self.semi_latus_rectum!r}"
            )
        if not (math.isfinite(self.eccentricity) and self.eccentricity >= 0.0):
            raise InvalidOrbitError(
                f"eccentricity must be non-negative finite, got {self.eccentricity!r}"
            )
        for name, val in (
            ("inclination", self.inclination),
            ("raan", self.raan),
            ("argument_of_periapsis", self.argument_of_periapsis),
            ("true_anomaly", self.true_anomaly),
            ("mu", self.mu),
        ):
            if not math.isfinite(val):
                raise InvalidOrbitError(f"{name} must be finite, got {val!r}")
        if self.mu <= 0.0:
            raise InvalidOrbitError(f"mu must be positive, got {self.mu!r}")

    @property
    def semi_major_axis(self) -> float:
        if self.is_parabolic:
            return math.inf
        return self.semi_latus_rectum / (1.0 - self.eccentricity ** 2)

    @property
    def semi_minor_axis(self) -> float:
        if self.eccentricity >= 1.0:
            return float("nan")
        a = self.semi_major_axis
        return a * math.sqrt(1.0 - self.eccentricity ** 2)

    @property
    def periapsis(self) -> float:
        return self.semi_latus_rectum / (1.0 + self.eccentricity)

    @property
    def apoapsis(self) -> float:
        if self.eccentricity >= 1.0:
            return math.inf
        return self.semi_latus_rectum / (1.0 - self.eccentricity)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "semi_latus_rectum": float(self.semi_latus_rectum),
            "eccentricity": float(self.eccentricity),
            "inclination": float(self.inclination),
            "raan": float(self.raan),
            "argument_of_periapsis": float(self.argument_of_periapsis),
            "true_anomaly": float(self.true_anomaly),
            "mu": float(self.mu),
            "is_circular": bool(self.is_circular),
            "is_equatorial": bool(self.is_equatorial),
            "is_parabolic": bool(self.is_parabolic),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ClassicalOrbitalElements":
        return cls(**d)


# ---------------------------------------------------------------------------
# State -> Elements
# ---------------------------------------------------------------------------

def state_to_elements(state: OrbitalState) -> ClassicalOrbitalElements:
    r_vec = state.position
    v_vec = state.velocity
    mu = state.mu

    r = r_vec.magnitude()
    v = v_vec.magnitude()
    if r == 0.0:
        raise DegenerateOrbitError("position is zero; orbit is undefined")

    h_vec = r_vec.cross(v_vec)
    h = h_vec.magnitude()
    if h < NODE_TOL:
        raise DegenerateOrbitError(
            "angular momentum is zero; orbit is degenerate (radial trajectory)"
        )

    # Eccentricity vector
    rv = r_vec.dot(v_vec)
    e_vec = ((v * v - mu / r) * r_vec - rv * v_vec) * (1.0 / mu)
    e = e_vec.magnitude()

    # Semi-latus rectum
    p = h * h / mu

    # Inclination
    cos_i = h_vec.z / h
    cos_i = max(-1.0, min(1.0, cos_i))
    i = math.acos(cos_i)

    # Node vector: n = z_hat x h
    n_vec = Vector3(-h_vec.y, h_vec.x, 0.0)
    n = n_vec.magnitude()

    is_circular = e < CIRCULAR_TOL
    is_equatorial = (i < EQUATORIAL_TOL) or (math.pi - i < EQUATORIAL_TOL)
    is_parabolic = abs(e - 1.0) < PARABOLIC_TOL

    # RAAN
    if not is_equatorial and n > NODE_TOL:
        raan = math.atan2(n_vec.y, n_vec.x) % (2.0 * math.pi)
    else:
        raan = 0.0

    # Argument of periapsis
    if is_circular:
        arg_p = 0.0
    elif not is_equatorial and n > NODE_TOL:
        # Angle from n_vec to e_vec, in the orbital plane, along the direction
        # of motion. (n x e) is parallel to h.
        cross_ne = n_vec.cross(e_vec)
        sin_t = cross_ne.dot(h_vec) / (n * e * h) if n * e * h > 0.0 else 0.0
        cos_t = n_vec.dot(e_vec) / (n * e)
        arg_p = math.atan2(sin_t, cos_t) % (2.0 * math.pi)
    else:
        # Equatorial (non-circular): use longitude of periapsis.
        arg_p = math.atan2(e_vec.y, e_vec.x) % (2.0 * math.pi)

    # True anomaly
    if not is_circular:
        cross_er = e_vec.cross(r_vec)
        sin_t = cross_er.dot(h_vec) / (e * r * h)
        cos_t = e_vec.dot(r_vec) / (e * r)
        true_anomaly = math.atan2(sin_t, cos_t) % (2.0 * math.pi)
    else:
        if not is_equatorial and n > NODE_TOL:
            # Argument of latitude from node to position
            cross_nr = n_vec.cross(r_vec)
            sin_t = cross_nr.dot(h_vec) / (n * r * h)
            cos_t = n_vec.dot(r_vec) / (n * r)
            true_anomaly = math.atan2(sin_t, cos_t) % (2.0 * math.pi)
        else:
            # Equatorial circular: true longitude from +x axis
            true_anomaly = math.atan2(r_vec.y, r_vec.x) % (2.0 * math.pi)

    return ClassicalOrbitalElements(
        semi_latus_rectum=p,
        eccentricity=e,
        inclination=i,
        raan=raan,
        argument_of_periapsis=arg_p,
        true_anomaly=true_anomaly,
        mu=mu,
        is_circular=is_circular,
        is_equatorial=is_equatorial,
        is_parabolic=is_parabolic,
    )


# ---------------------------------------------------------------------------
# Elements -> State
# ---------------------------------------------------------------------------

def _rotation_pqw_to_ijk(i: float, raan: float, arg_p: float) -> Matrix3:
    """Return the rotation matrix from perifocal (PQW) to inertial (IJK)."""
    cO, sO = math.cos(raan), math.sin(raan)
    ci, si = math.cos(i), math.sin(i)
    cw, sw = math.cos(arg_p), math.sin(arg_p)
    return Matrix3(
        cO * cw - sO * ci * sw, -cO * sw - sO * ci * cw,  sO * si,
        sO * cw + cO * ci * sw, -sO * sw + cO * ci * cw, -cO * si,
        si * sw,                 si * cw,                 ci,
    )


def elements_to_state(elements: ClassicalOrbitalElements,
                      epoch: float = 0.0) -> OrbitalState:
    p = elements.semi_latus_rectum
    e = elements.eccentricity
    nu = elements.true_anomaly
    mu = elements.mu

    cos_nu = math.cos(nu)
    sin_nu = math.sin(nu)

    denom = 1.0 + e * cos_nu
    if denom <= 0.0:
        raise InvalidOrbitError(
            f"true anomaly gives non-positive radius (1 + e cos nu = {denom!r})"
        )

    r_mag = p / denom
    r_pqw = Vector3(r_mag * cos_nu, r_mag * sin_nu, 0.0)

    v_factor = math.sqrt(mu / p)
    v_pqw = Vector3(-v_factor * sin_nu, v_factor * (e + cos_nu), 0.0)

    M = _rotation_pqw_to_ijk(elements.inclination,
                             elements.raan,
                             elements.argument_of_periapsis)
    r_ijk = M.transform(r_pqw)
    v_ijk = M.transform(v_pqw)
    return OrbitalState(position=r_ijk, velocity=v_ijk,
                        mu=mu, epoch=epoch)
