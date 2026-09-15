"""ASTRA Spacecraft Physics layer.

Dependency direction:
    CORE -> MATHEMATICS -> MOTION -> PHYSICS -> ORBITAL -> NBODY
         -> SPACECRAFT -> (future systems)

Scope
-----
Spacecraft-specific physical behaviour: mass accounting (dry + propellant),
engines (thrust, Isp), propellant consumption, finite and impulsive burns,
rocket-equation delta-v, engine torque, and integration with Motion,
Physics, Orbital Mechanics, and N-Body gravity.

Boundaries respected:
- Motion owns kinematic state and integration.
- Physics owns generic force/torque/momentum/mass primitives.
- Orbital Mechanics owns orbital elements and impulsive maneuver math.
- N-Body owns many-body gravity.
- Spacecraft Physics executes physical maneuvers; it does not plan them.

Determinism: engines and burns stored in ordered lists; no global RNG, no
wall-clock; iteration is deterministic.

Authority: mutating operations require CORE simulation-thread authority.
"""
from astra.spacecraft.errors import (
    SpacecraftError, InvalidMassError as SpacecraftInvalidMassError,
    InvalidEngineError, InvalidBurnError, PropellantExhaustedError,
    InvalidRocketEquationError,
)
from astra.spacecraft.constants import (
    G0, DEFAULT_ISP_TOL, MIN_ISP, MAX_ISP,
    MIN_THRUST, PROP_TOL,
)
from astra.spacecraft.mass import SpacecraftMass
from astra.spacecraft.engines import Engine, EngineSpec
from astra.spacecraft.burns import (
    BurnKind, BurnState,
    FiniteBurn, ImpulsiveBurn,
)
from astra.spacecraft.rocket import (
    rocket_delta_v, propellant_for_delta_v,
    remaining_delta_v, mass_after_delta_v,
)
from astra.spacecraft.dynamics import (
    engine_mass_flow, engine_thrust_world, engine_torque_world,
    evaluate_engines, EngineEvaluation,
)
from astra.spacecraft.state import SpacecraftState
from astra.spacecraft.components import SpacecraftComponent
from astra.spacecraft.system import SpacecraftSystem, GravityProvider

__all__ = [
    "SpacecraftError", "SpacecraftInvalidMassError",
    "InvalidEngineError", "InvalidBurnError",
    "PropellantExhaustedError", "InvalidRocketEquationError",
    "G0", "DEFAULT_ISP_TOL", "MIN_ISP", "MAX_ISP",
    "MIN_THRUST", "PROP_TOL",
    "SpacecraftMass",
    "Engine", "EngineSpec",
    "BurnKind", "BurnState",
    "FiniteBurn", "ImpulsiveBurn",
    "rocket_delta_v", "propellant_for_delta_v",
    "remaining_delta_v", "mass_after_delta_v",
    "engine_mass_flow", "engine_thrust_world", "engine_torque_world",
    "evaluate_engines", "EngineEvaluation",
    "SpacecraftState",
    "SpacecraftComponent",
    "SpacecraftSystem", "GravityProvider",
]
