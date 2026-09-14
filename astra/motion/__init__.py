"""ASTRA Motion layer.

Dependency direction:
    CORE -> MATHEMATICS -> MOTION -> PHYSICS -> ...

Conventions
-----------
- Right-handed Cartesian coordinates; radians.
- MotionState.position / velocity / acceleration are in the SIMULATION WORLD
  frame (absolute / physical) and are NOT modified by an origin rebase;
  only frame-local views change.
- Orientation is a unit Quaternion mapping body -> world: q * v_body * q^-1 = v_world.
- Angular velocity is expressed in the WORLD frame; dq/dt = 0.5 * omega_quat * q.
- Deterministic: no global RNG, no wall-clock reads, fixed input order.
"""
from astra.motion.state import MotionState
from astra.motion.components import MotionComponent
from astra.motion.integrators import (
    Integrator, ExplicitEulerIntegrator,
    SemiImplicitEulerIntegrator, RK4Integrator,
)
from astra.motion.system import MotionSystem
from astra.motion.frames import (
    to_frame_local, from_frame_local, world_position, rebase_invariant_state,
)
from astra.motion.state import (
    MotionError, InvalidMotionStateError, InvalidTimestepError,
    validate_timestep,
)

__all__ = [
    "MotionState", "MotionComponent",
    "Integrator", "ExplicitEulerIntegrator",
    "SemiImplicitEulerIntegrator", "RK4Integrator",
    "MotionSystem",
    "to_frame_local", "from_frame_local", "world_position",
    "rebase_invariant_state",
    "MotionError", "InvalidMotionStateError", "InvalidTimestepError",
    "validate_timestep",
]
