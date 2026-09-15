"""Impact geometry computation.

Conventions
-----------
- All vectors live in the world frame (caller is responsible for frame
  consistency; ImpactEvent.reference_frame records which frame was used).
- ``incoming_direction`` is the UNIT vector of the impactor's velocity
  relative to the target.
- ``surface_normal`` is the OUTWARD unit normal of the target at contact.
- ``incidence_angle_rad`` = angle between -incoming and the normal:
  0 = head-on, pi/2 = grazing.

Degenerate cases
----------------
- Zero relative velocity        -> ImpactValidationError (no impact)
- Coincident centres            -> normal falls back to -incoming (deterministic)
- Target radius 0 (point body)  -> contact is the target position
"""
from __future__ import annotations

import math

from astra.mathematics import Vector3

from .config import DestructionConfig
from .errors import ImpactValidationError, NumericalError
from .types import ImpactEvent, ImpactGeometry


def _normalized(v: Vector3, name: str) -> Vector3:
    try:
        return v.normalized()
    except ZeroDivisionError as exc:
        raise NumericalError(f"cannot normalize zero-length {name}") from exc


def compute_impact_geometry(event: ImpactEvent, config: DestructionConfig) -> ImpactGeometry:
    rel_v = event.relative_velocity()
    speed = rel_v.magnitude()
    if speed == 0.0:
        raise ImpactValidationError("relative velocity is zero; impact undefined")

    incoming = rel_v / speed

    delta = event.impactor_position - event.target_position
    d = delta.magnitude()

    if d == 0.0:
        # Coincident centres: deterministic fallback, approach defines normal.
        contact = event.target_position
        surface_normal = -incoming
    else:
        dir_centres = delta / d
        radius = event.target_radius_m
        if radius > 0.0:
            # Spherical target: project contact onto the sphere when the
            # impactor is still outside it, else take the midpoint of the
            # penetrating segment (documented approximation).
            offset = radius if d > radius else d * 0.5
            contact = event.target_position + dir_centres * offset
        else:
            # Point target: contact is the target position.
            contact = event.target_position
        surface_normal = dir_centres

    cos_incidence = max(-1.0, min(1.0, (-incoming).dot(surface_normal)))
    incidence = math.acos(cos_incidence)

    # Grazing: approach nearly parallel to the local surface plane, i.e.
    # grazing elevation near 0; sin(elevation) == cos(incidence).
    is_grazing = cos_incidence <= config.grazing_sin_threshold
    is_head_on = incidence <= config.head_on_angle_threshold_rad

    return ImpactGeometry(
        contact_point=contact,
        surface_normal=surface_normal,
        incoming_direction=incoming,
        incidence_angle_rad=incidence,
        is_grazing=is_grazing,
        is_head_on=is_head_on,
    )
