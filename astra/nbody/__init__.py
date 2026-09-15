"""ASTRA N-Body Mechanics layer.

Dependency direction:
    CORE -> MATHEMATICS -> MOTION -> PHYSICS -> ORBITAL -> NBODY -> ...

Newtonian many-body gravitational dynamics.

Conventions
-----------
- Positions / velocities are in a single inertial frame (absolute).
- Gravitational constant and default softening are imported from
  astra.physics.constants. No duplication.
- Newtonian: F_ij = G m_i m_j (r_j - r_i) / (|r_j - r_i|^2 + eps^2)^(3/2)
- Acceleration of body i: a_i = sum_j G m_j (r_j - r_i) / (r^2 + eps^2)^(3/2)
- Integrator: velocity Verlet (symplectic, second-order, standard for
  gravitational N-body). Not a new ODE engine; a thin domain-specific
  composition on top of astra.mathematics primitives.
- Determinism: bodies are stored as a list; pairs are evaluated in
  index order i < j; no global RNG, no wall-clock, no unordered iteration.
- Authority: mutating operations require CORE simulation-thread authority.

Units: SI-coherent (metre, second, kg, radian).
"""
from astra.nbody.errors import (
    NBodyError, InvalidBodyError, InvalidMassError as NBodyInvalidMassError,
    DuplicateBodyError, NBodySingularityError, InvalidTimestepError,
)
from astra.nbody.constants import (
    DEFAULT_SOFTENING as NBODY_DEFAULT_SOFTENING,
    MIN_SOFTENING, ACC_TOL, ENERGY_TOL,
)
from astra.nbody.bodies import NBodyBody
from astra.nbody.gravity import (
    pairwise_acceleration, pairwise_potential, compute_accelerations,
    gravitational_potential_energy,
)
from astra.nbody.barycenter import (
    total_mass, center_of_mass, center_of_mass_velocity,
    to_barycentric, from_barycentric,
)
from astra.nbody.diagnostics import (
    total_linear_momentum, total_angular_momentum,
    kinetic_energy, total_energy, momentum_drift, energy_drift,
)
from astra.nbody.integration import velocity_verlet_step
from astra.nbody.system import NBodySystem

__all__ = [
    # errors
    "NBodyError", "InvalidBodyError", "NBodyInvalidMassError",
    "DuplicateBodyError", "NBodySingularityError", "InvalidTimestepError",
    # constants
    "NBODY_DEFAULT_SOFTENING", "MIN_SOFTENING", "ACC_TOL", "ENERGY_TOL",
    # bodies
    "NBodyBody",
    # gravity
    "pairwise_acceleration", "pairwise_potential",
    "compute_accelerations", "gravitational_potential_energy",
    # barycenter
    "total_mass", "center_of_mass", "center_of_mass_velocity",
    "to_barycentric", "from_barycentric",
    # diagnostics
    "total_linear_momentum", "total_angular_momentum",
    "kinetic_energy", "total_energy",
    "momentum_drift", "energy_drift",
    # integration
    "velocity_verlet_step",
    # system
    "NBodySystem",
]
