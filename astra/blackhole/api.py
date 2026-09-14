"""ASTRA Black-Hole - authoritative facade API.

Contract: external systems (Orbital, Spacecraft, future Spacetime engines)
query THIS module only; the subsystem modules are internal mathematics.
The facade dispatches on ``BlackHoleState.model`` so callers never
hand-select Schwarzschild vs Kerr formulas.

Dependency direction (no reverse edges, no cycles):
    CORE -> MATHEMATICS -> PHYSICS -> RELATIVITY -> BLACKHOLE -> (Spacetime)

Deterministic pure functions over an immutable state object.
"""

from __future__ import annotations

import math
from typing import Dict

from astra.blackhole import kerr, schwarzschild
from astra.blackhole.models import BlackHoleModel
from astra.blackhole.parameters import BlackHoleState


def create_black_hole(mass_kg: float, spin_param: float = 0.0) -> BlackHoleState:
    """Create and validate an immutable BlackHoleState.

    spin_param = 0 yields the Schwarzschild model; any non-zero spin within
    [-1, 1] yields Kerr. Naked singularities (|spin| > 1), non-positive or
    non-finite masses are rejected (see astra.blackhole.exceptions).
    """
    return BlackHoleState(mass_kg=mass_kg, spin_param=spin_param)


def get_schwarzschild_boundaries(bh_state: BlackHoleState) -> Dict[str, float]:
    """Key geometric boundaries of the Schwarzschild geometry (metres).

    Keys: schwarzschild_radius (r_s), gravitational_radius (r_g = r_s/2),
    photon_sphere_radius (1.5 r_s), isco_radius (3 r_s).
    """
    rs = schwarzschild.schwarzschild_radius_m(bh_state.mass_kg)
    return {
        "schwarzschild_radius": rs,
        "gravitational_radius": 0.5 * rs,
        "photon_sphere_radius": schwarzschild.photon_sphere_radius(bh_state.mass_kg),
        "isco_radius": schwarzschild.isco_radius(bh_state.mass_kg),
    }


def get_kerr_boundaries(bh_state: BlackHoleState) -> Dict[str, float]:
    """Key geometric boundaries of the Kerr geometry (metres).

    Keys: r_plus, r_minus, ergosphere_equatorial, ergosphere_polar,
    isco_prograde, isco_retrograde, photon_orbit_prograde,
    photon_orbit_retrograde.
    """
    r_plus, r_minus = kerr.horizons(bh_state)
    return {
        "r_plus": r_plus,
        "r_minus": r_minus,
        "ergosphere_equatorial": kerr.ergosphere_radius(bh_state, math.pi / 2),
        "ergosphere_polar": kerr.ergosphere_radius(bh_state, 0.0),
        "isco_prograde": kerr.isco_prograde(bh_state),
        "isco_retrograde": kerr.isco_retrograde(bh_state),
        "photon_orbit_prograde": kerr.photon_orbit_prograde(bh_state),
        "photon_orbit_retrograde": kerr.photon_orbit_retrograde(bh_state),
    }


def calculate_ergosphere_radius(bh_state: BlackHoleState, theta_rad: float) -> float:
    """Static-limit radius r_E(theta) (m). Defined for both models
    (constant 2 r_g = r_s for Schwarzschild)."""
    return kerr.ergosphere_radius(bh_state, theta_rad)


def gravitational_time_dilation(bh_state: BlackHoleState, radius: float) -> float:
    """Static-clock time dilation dt/dtau at a radius (dimensionless).

    SCHWARZSCHILD: dt/dtau = 1/sqrt(1 - r_s/r) outside the horizon guard.
    KERR: equatorial static observers, valid only outside the ergosphere.

    Raises CoordinateSingularityError at or inside the applicable boundary.
    """
    if bh_state.model is BlackHoleModel.KERR:
        return kerr.static_time_dilation_equatorial(bh_state, radius)
    return schwarzschild.gravitational_time_dilation(bh_state, radius)


def gravitational_redshift(
    bh_state: BlackHoleState, r_emitter: float, r_observer: float
) -> float:
    """Gravitational redshift z between static radii (dimensionless).

    Exact for Schwarzschild everywhere outside the horizon guard and for
    Kerr on the equatorial plane outside the ergosphere (where g_tt takes
    the same form). Blueshift (z < 0) when the observer is deeper.
    """
    if bh_state.model is BlackHoleModel.KERR:
        ergo = kerr.ergosphere_radius(bh_state, math.pi / 2)
        if r_emitter <= ergo or r_observer <= ergo:
            # Delegate the precise epsilon policy error to the subsystem.
            return schwarzschild.gravitational_redshift(bh_state, r_emitter, r_observer)
    return schwarzschild.gravitational_redshift(bh_state, r_emitter, r_observer)


def equatorial_frame_dragging_velocity(bh_state: BlackHoleState, radius: float) -> float:
    """Tangential frame-dragging speed v = omega * r (m/s) in the equatorial
    plane at the given radius.

    Exactly 0.0 for the Schwarzschild model (no frame dragging). Raises
    CoordinateSingularityError at/inside the outer horizon for Kerr.
    """
    if bh_state.model is BlackHoleModel.SCHWARZSCHILD:
        return 0.0
    omega = kerr.frame_dragging_angular_velocity(bh_state, radius, math.pi / 2)
    return omega * radius
