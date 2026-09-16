"""ASTRA Orbital Mechanics layer.

Dependency direction:
    CORE -> MATHEMATICS -> MOTION -> PHYSICS -> ORBITAL -> ...

Conventions
-----------
- Classical Newtonian two-body problem.
- Positions / velocities are RELATIVE to the central body (not barycentric).
- Gravitational parameter mu = G * (M + m); for m << M, mu ~= G*M.
- Right-handed Cartesian; angles in radians.
- Mean motion n = sqrt(mu / |a|^3).
- Standard 3-1-3 Euler sequence for elements:
    R_z(omega) . R_x(i) . R_z(Omega) : inertial -> perifocal.
- Anomalies: true nu, eccentric E, hyperbolic H, mean M.
  Elliptic M = E - e sin E;  Hyperbolic M = e sinh H - H.

Determinism: no wall-clock, no RNG, deterministic iteration order.

Units: SI-coherent (metre, second, kg, radian).
"""
from astra.orbital.errors import (
    OrbitalError, DegenerateOrbitError, InvalidOrbitError,
    KeplerConvergenceError, InvalidTransferError,
)
from astra.orbital.constants import (
    CIRCULAR_TOL, EQUATORIAL_TOL, PARABOLIC_TOL, NODE_TOL,
    KEPLER_TOL, KEPLER_MAX_ITER,
)
from astra.orbital.state import OrbitalState
from astra.orbital.elements import (
    ClassicalOrbitalElements, state_to_elements, elements_to_state,
)
from astra.orbital.conics import (
    ConicType, classify_conic, is_elliptic, is_parabolic, is_hyperbolic,
)
from astra.orbital.anomalies import (
    true_to_eccentric, eccentric_to_true,
    true_to_hyperbolic, hyperbolic_to_true,
    true_to_mean_elliptic, mean_to_true_elliptic,
    true_to_mean_hyperbolic, mean_to_true_hyperbolic,
    true_to_mean_parabolic, mean_to_true_parabolic,
)
from astra.orbital.kepler import (
    solve_kepler_elliptic, solve_kepler_hyperbolic, solve_barker,
)
from astra.orbital.propagation import propagate, propagate_state
from astra.orbital.velocities import (
    vis_viva, circular_velocity, escape_velocity,
    periapsis_velocity, apoapsis_velocity,
)
from astra.orbital.period import orbital_period
from astra.orbital.energy import specific_orbital_energy, specific_angular_momentum
from astra.orbital.maneuvers import (
    plane_change_delta_v, circularize_delta_v, impulsive_delta_v,
)
from astra.orbital.transfers import (
    HohmannTransfer, BiellipticTransfer,
    hohmann_transfer, bielliptic_transfer,
)
from astra.orbital.windows import synodic_period, phase_angle_for_rendezvous

__all__ = [
    # errors
    "OrbitalError", "DegenerateOrbitError", "InvalidOrbitError",
    "KeplerConvergenceError", "InvalidTransferError",
    # constants
    "CIRCULAR_TOL", "EQUATORIAL_TOL", "PARABOLIC_TOL", "NODE_TOL",
    "KEPLER_TOL", "KEPLER_MAX_ITER",
    # state / elements
    "OrbitalState", "ClassicalOrbitalElements",
    "state_to_elements", "elements_to_state",
    # conics
    "ConicType", "classify_conic",
    "is_elliptic", "is_parabolic", "is_hyperbolic",
    # anomalies
    "true_to_eccentric", "eccentric_to_true",
    "true_to_hyperbolic", "hyperbolic_to_true",
    "true_to_mean_elliptic", "mean_to_true_elliptic",
    "true_to_mean_hyperbolic", "mean_to_true_hyperbolic",
    "true_to_mean_parabolic", "mean_to_true_parabolic",
    # kepler
    "solve_kepler_elliptic", "solve_kepler_hyperbolic", "solve_barker",
    # propagation
    "propagate", "propagate_state",
    # velocities
    "vis_viva", "circular_velocity", "escape_velocity",
    "periapsis_velocity", "apoapsis_velocity",
    # period
    "orbital_period",
    # energy
    "specific_orbital_energy", "specific_angular_momentum",
    # maneuvers
    "plane_change_delta_v", "circularize_delta_v", "impulsive_delta_v",
    # transfers
    "HohmannTransfer", "BiellipticTransfer",
    "hohmann_transfer", "bielliptic_transfer",
    # windows
    "synodic_period", "phase_angle_for_rendezvous",
]
