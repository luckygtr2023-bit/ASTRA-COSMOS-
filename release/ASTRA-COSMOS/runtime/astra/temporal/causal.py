"""ASTRA Temporal - causal classification, ordering, and light cones.

Contract: causal structure is decided by the ACTIVE metric through
``astra.spacetime.causality`` (signature (-,+,+,+), x^mu = (ct, ...)) -
this module adds ORDERING and ACCESSIBILITY semantics on top, never a new
interval computation.

Ordering policy (physical, not convenient):
    - TIMELIKE or NULL separation: the ordering is invariant; chart time
      decides A_PRECEDES_B / B_PRECEDES_A (equal t with null separation is
      impossible; equal t with timelike separation is impossible).
    - SPACELIKE separation: CAUSALLY_DISCONNECTED. No total order is
      imposed - physically, different inertial frames disagree, and this
      API refuses to fake one.
    - Identical coordinates (exact): COINCIDENT.

Light cones: region membership (inside/on/spacelike exterior, future vs
past by chart time), causal accessibility (can B follow A?), and null
generators for DIAGONAL metrics via the spacetime layer's
``null_ray_directions`` (documented limitation inherited).

ANALYSIS =/= EXECUTION: nothing here moves anything anywhere; see the
package docstring for the explicit time-travel boundary.

Deterministic pure functions.
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Sequence, Tuple

from astra.spacetime.causality import classify_interval, null_ray_directions
from astra.spacetime.exceptions import InvalidCoordinateError
from astra.spacetime.metric import MetricField, _validate_coords
from astra.temporal.exceptions import InvalidTemporalStateError


class CausalRelation(Enum):
    """Deterministic causal relationship between two events."""

    COINCIDENT = "COINCIDENT"
    A_PRECEDES_B = "A_PRECEDES_B"
    B_PRECEDES_A = "B_PRECEDES_A"
    CAUSALLY_DISCONNECTED = "CAUSALLY_DISCONNECTED"


class LightConeRegion(Enum):
    """Membership of event B relative to event A's light cone."""

    COINCIDENT = "COINCIDENT"
    INSIDE_FUTURE_CONE = "INSIDE_FUTURE_CONE"      # timelike, t_B > t_A
    ON_FUTURE_CONE = "ON_FUTURE_CONE"              # null,      t_B > t_A
    INSIDE_PAST_CONE = "INSIDE_PAST_CONE"          # timelike,  t_B < t_A
    ON_PAST_CONE = "ON_PAST_CONE"                  # null,      t_B < t_A
    SPACELIKE_EXTERIOR = "SPACELIKE_EXTERIOR"


def _validated_pair(metric: MetricField, a: Sequence[float], b: Sequence[float]):
    xa = _validate_coords(a, metric.chart)
    xb = _validate_coords(b, metric.chart)
    return xa, xb


def classify(metric: MetricField, a: Sequence[float], b: Sequence[float],
             tolerance: float = 1.0e-9):
    """TIMELIKE / NULL / SPACELIKE via the spacetime layer (active metric)."""
    xa, xb = _validated_pair(metric, a, b)
    return classify_interval(metric, xa, xb, tolerance)


def relate(metric: MetricField, a: Sequence[float], b: Sequence[float],
           tolerance: float = 1.0e-9) -> CausalRelation:
    """Deterministic causal relation (see module ordering policy)."""
    xa, xb = _validated_pair(metric, a, b)
    if xa == xb:
        return CausalRelation.COINCIDENT
    kind = classify_interval(metric, xa, xb, tolerance)
    if kind.value == "SPACELIKE":
        return CausalRelation.CAUSALLY_DISCONNECTED
    # Timelike/null: ordering is invariant; chart time decides.
    if xb[0] > xa[0]:
        return CausalRelation.A_PRECEDES_B
    if xb[0] < xa[0]:
        return CausalRelation.B_PRECEDES_A
    # Same chart time but non-spacelike cannot happen in a Lorentzian patch
    # (a non-spacelike separation with dt = 0 is spacelike); reaching here
    # implies tolerance-band edge cases - report honestly.
    return CausalRelation.CAUSALLY_DISCONNECTED


def light_cone_region(metric: MetricField, a: Sequence[float], b: Sequence[float],
                      tolerance: float = 1.0e-9) -> LightConeRegion:
    """Where B sits relative to A's light cone (future/past, inside/on)."""
    xa, xb = _validated_pair(metric, a, b)
    if xa == xb:
        return LightConeRegion.COINCIDENT
    kind = classify_interval(metric, xa, xb, tolerance)
    if kind.value == "SPACELIKE":
        return LightConeRegion.SPACELIKE_EXTERIOR
    future = xb[0] > xa[0]
    if kind.value == "NULL":
        return LightConeRegion.ON_FUTURE_CONE if future else LightConeRegion.ON_PAST_CONE
    return (LightConeRegion.INSIDE_FUTURE_CONE if future
            else LightConeRegion.INSIDE_PAST_CONE)


def is_causally_accessible(metric: MetricField, a: Sequence[float],
                           b: Sequence[float], tolerance: float = 1.0e-9) -> bool:
    """True iff B can causally follow A: inside or on A's future cone.

    A physical signal may be timelike or null - never faster. FTL
    accessibility is intentionally NOT provided anywhere in this layer.
    """
    region = light_cone_region(metric, a, b, tolerance)
    return region in (LightConeRegion.INSIDE_FUTURE_CONE, LightConeRegion.ON_FUTURE_CONE)


def cone_null_generators(metric: MetricField, a: Sequence[float],
                         spatial_directions: Sequence[Sequence[float]]
                         ) -> Tuple[Tuple[Tuple[float, float, float, float], ...], ...]:
    """Null tangent generators of the light cone at event A.

    Delegates per direction to ``astra.spacetime.causality.null_ray_``
    ``directions`` (future, past) - diagonal metrics only, limitation
    inherited and documented there.
    """
    xa = _validate_coords(a, metric.chart)
    out = []
    for direction in spatial_directions:
        out.append(null_ray_directions(metric, xa, direction))
    return tuple(out)
