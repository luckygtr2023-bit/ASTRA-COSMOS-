"""Burn representations: finite-duration and impulsive.

- FiniteBurn: engine target + body-frame thrust direction + duration.
  Executed by SpacecraftSystem over multiple timesteps.
- ImpulsiveBurn: instantaneous delta-v vector. Executed by the caller
  (usually via SpacecraftSystem.apply_impulsive).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional
import math

from astra.mathematics import Vector3
from astra.spacecraft.errors import InvalidBurnError


class BurnKind(Enum):
    FINITE = "finite"
    IMPULSIVE = "impulsive"


@dataclass
class BurnState:
    """Mutable progress state for an active burn."""
    kind: BurnKind
    remaining_time: float = 0.0       # for finite burns
    remaining_delta_v: float = 0.0    # for impulsive burns
    completed: bool = False
    cancelled: bool = False


@dataclass
class FiniteBurn:
    """Requested finite burn.

    Fields
    ------
    id                 : str, unique identifier for the burn
    engine_id          : str, which engine to use (must exist on spacecraft)
    thrust_direction_local : body-frame direction of thrust; if None, the
                            engine's own direction is used.
    duration           : requested burn duration (s), > 0
    """
    id: str
    engine_id: str
    duration: float
    thrust_direction_local: Optional[Vector3] = None

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id:
            raise InvalidBurnError("burn id must be a non-empty string")
        if not isinstance(self.engine_id, str) or not self.engine_id:
            raise InvalidBurnError("engine_id must be a non-empty string")
        if not (math.isfinite(self.duration) and self.duration > 0.0):
            raise InvalidBurnError(
                f"duration must be positive finite, got {self.duration!r}"
            )
        if self.thrust_direction_local is not None:
            if not self.thrust_direction_local.is_finite():
                raise InvalidBurnError("thrust_direction_local must be finite")
            if self.thrust_direction_local.is_zero():
                raise InvalidBurnError("thrust_direction_local must be non-zero")


@dataclass
class ImpulsiveBurn:
    """Idealized instantaneous delta-v.

    Fields
    ------
    id        : str, unique identifier
    delta_v   : Vector3, world-frame velocity change (m/s)
    """
    id: str
    delta_v: Vector3

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id:
            raise InvalidBurnError("burn id must be a non-empty string")
        if not self.delta_v.is_finite():
            raise InvalidBurnError("delta_v must be finite")


def finite_burn_to_dict(b: FiniteBurn) -> Dict[str, Any]:
    return {
        "kind": BurnKind.FINITE.value,
        "id": b.id,
        "engine_id": b.engine_id,
        "duration": float(b.duration),
        "thrust_direction_local": (
            list(b.thrust_direction_local.to_tuple())
            if b.thrust_direction_local is not None else None
        ),
    }


def finite_burn_from_dict(d: Dict[str, Any]) -> FiniteBurn:
    td = d.get("thrust_direction_local")
    return FiniteBurn(
        id=str(d["id"]),
        engine_id=str(d["engine_id"]),
        duration=float(d["duration"]),
        thrust_direction_local=(Vector3.from_tuple(td) if td is not None else None),
    )


def impulsive_burn_to_dict(b: ImpulsiveBurn) -> Dict[str, Any]:
    return {
        "kind": BurnKind.IMPULSIVE.value,
        "id": b.id,
        "delta_v": list(b.delta_v.to_tuple()),
    }


def impulsive_burn_from_dict(d: Dict[str, Any]) -> ImpulsiveBurn:
    return ImpulsiveBurn(id=str(d["id"]),
                        delta_v=Vector3.from_tuple(d["delta_v"]))
