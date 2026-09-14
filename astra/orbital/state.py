"""OrbitalState — relative two-body state (position + velocity, mu, epoch)."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict
import math

from astra.mathematics import Vector3
from astra.orbital.errors import InvalidOrbitError


@dataclass(frozen=True)
class OrbitalState:
    """Two-body state relative to the central body.

    Fields
    ------
    position:  Vector3, position of the body relative to central body (m)
    velocity:  Vector3, velocity relative to the central body (m/s)
    mu:        float, gravitational parameter G(M+m) (m^3/s^2). mu > 0.
    epoch:     float, simulation time at which state is valid (s). Default 0.
    """
    position: Vector3
    velocity: Vector3
    mu: float
    epoch: float = 0.0

    def __post_init__(self):
        if not self.position.is_finite():
            raise InvalidOrbitError("position must be finite")
        if not self.velocity.is_finite():
            raise InvalidOrbitError("velocity must be finite")
        if not (math.isfinite(self.mu) and self.mu > 0.0):
            raise InvalidOrbitError(f"mu must be positive finite, got {self.mu!r}")
        if not math.isfinite(self.epoch):
            raise InvalidOrbitError(f"epoch must be finite, got {self.epoch!r}")

    @property
    def r(self) -> float:
        return self.position.magnitude()

    @property
    def v(self) -> float:
        return self.velocity.magnitude()

    @property
    def h_vec(self) -> Vector3:
        return self.position.cross(self.velocity)

    @property
    def h(self) -> float:
        return self.h_vec.magnitude()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "position": list(self.position.to_tuple()),
            "velocity": list(self.velocity.to_tuple()),
            "mu": float(self.mu),
            "epoch": float(self.epoch),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "OrbitalState":
        return cls(
            position=Vector3.from_tuple(d["position"]),
            velocity=Vector3.from_tuple(d["velocity"]),
            mu=float(d["mu"]),
            epoch=float(d.get("epoch", 0.0)),
        )
