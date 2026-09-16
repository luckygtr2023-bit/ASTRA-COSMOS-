"""Mass and inertia properties for Physics bodies.

A MassProperties instance is immutable, hashable, and independent of any
entity or MotionState. It is the physical quantity description:
    mass, inverse_mass, inertia_body, inverse_inertia_body

Body frame vs world frame
-------------------------
- inertia_body / inverse_inertia_body are BODY-frame tensors.
- To obtain world-frame quantities at a given body orientation q, use
  `world_inertia(q)` and `world_inverse_inertia(q)`, which compute
  R I R^T and R I^-1 R^T respectively (R = q.to_matrix3()).

Static bodies
-------------
- Static bodies (mass = +inf, inverse_mass = 0) do not respond to force
  or torque. They may still act as gravity sources.

Point masses
------------
- Point masses (from `point_mass`) have zero inertia. Applied torque
  produces zero angular acceleration. This is explicit, not a bug.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict
import math

from astra.mathematics import Matrix3, Quaternion
from astra.physics.errors import InvalidMassError
from astra.physics.validation import validate_mass, validate_inertia


@dataclass(frozen=True)
class MassProperties:
    mass: float
    inverse_mass: float
    inertia_body: Matrix3
    inverse_inertia_body: Matrix3

    def __post_init__(self):
        validate_mass(self.mass, allow_inf=True)
        if math.isnan(self.inverse_mass) or self.inverse_mass < 0.0:
            raise InvalidMassError(
                f"inverse_mass must be non-negative finite, got {self.inverse_mass!r}"
            )
        if not self.inertia_body.is_finite():
            raise InvalidMassError("inertia_body must be finite")
        if not self.inverse_inertia_body.is_finite():
            raise InvalidMassError("inverse_inertia_body must be finite")

    @property
    def is_static(self) -> bool:
        return self.inverse_mass == 0.0

    @property
    def is_point_mass(self) -> bool:
        """True if this body has no rotational inertia (inverse_inertia == 0)."""
        return self.inverse_inertia_body == Matrix3.zeros()

    # -- factories --

    @classmethod
    def static(cls) -> "MassProperties":
        return cls(
            mass=math.inf,
            inverse_mass=0.0,
            inertia_body=Matrix3.zeros(),
            inverse_inertia_body=Matrix3.zeros(),
        )

    @classmethod
    def point_mass(cls, mass: float) -> "MassProperties":
        validate_mass(mass, allow_inf=False)
        return cls(
            mass=mass,
            inverse_mass=1.0 / mass,
            inertia_body=Matrix3.zeros(),
            inverse_inertia_body=Matrix3.zeros(),
        )

    @classmethod
    def from_scalar_inertia(cls, mass: float, inertia: float) -> "MassProperties":
        validate_mass(mass, allow_inf=False)
        validate_inertia(inertia)
        I = Matrix3.diagonal(inertia, inertia, inertia)
        inv_I = Matrix3.diagonal(1.0 / inertia, 1.0 / inertia, 1.0 / inertia)
        return cls(mass=mass, inverse_mass=1.0 / mass,
                   inertia_body=I, inverse_inertia_body=inv_I)

    @classmethod
    def from_tensor(cls, mass: float, inertia: Matrix3) -> "MassProperties":
        validate_mass(mass, allow_inf=False)
        det = inertia.determinant()
        if not (math.isfinite(det) and det > 0.0):
            raise InvalidMassError(
                f"inertia tensor must be positive-definite, det={det!r}"
            )
        inv_I = inertia.inverse()
        return cls(mass=mass, inverse_mass=1.0 / mass,
                   inertia_body=inertia, inverse_inertia_body=inv_I)

    @classmethod
    def sphere(cls, mass: float, radius: float) -> "MassProperties":
        validate_mass(mass, allow_inf=False)
        validate_inertia(radius)
        I = (2.0 / 5.0) * mass * radius * radius
        return cls.from_scalar_inertia(mass, I)

    @classmethod
    def solid_box(cls, mass: float, sx: float, sy: float, sz: float) -> "MassProperties":
        validate_mass(mass, allow_inf=False)
        for s in (sx, sy, sz):
            if not (math.isfinite(s) and s > 0.0):
                raise InvalidMassError(f"box side must be positive finite, got {s!r}")
        Ix = (1.0 / 12.0) * mass * (sy * sy + sz * sz)
        Iy = (1.0 / 12.0) * mass * (sx * sx + sz * sz)
        Iz = (1.0 / 12.0) * mass * (sx * sx + sy * sy)
        return cls.from_tensor(mass, Matrix3.diagonal(Ix, Iy, Iz))

    # -- world-frame inertia --

    def world_inertia(self, orientation: Quaternion) -> Matrix3:
        R = orientation.to_matrix3()
        return R.matmul(self.inertia_body).matmul(R.transpose())

    def world_inverse_inertia(self, orientation: Quaternion) -> Matrix3:
        R = orientation.to_matrix3()
        return R.matmul(self.inverse_inertia_body).matmul(R.transpose())

    # -- serialization --

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mass": float(self.mass),
            "inverse_mass": float(self.inverse_mass),
            "inertia_body": list(self.inertia_body.to_tuple()),
            "inverse_inertia_body": list(self.inverse_inertia_body.to_tuple()),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MassProperties":
        return cls(
            mass=float(d["mass"]),
            inverse_mass=float(d["inverse_mass"]),
            inertia_body=Matrix3(*d["inertia_body"]),
            inverse_inertia_body=Matrix3(*d["inverse_inertia_body"]),
        )
