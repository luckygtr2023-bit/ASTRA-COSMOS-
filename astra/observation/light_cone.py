"""Light cones — past/future, observability, causal accessibility.

Delegates interval classification to the ACTIVE metric via
astra.spacetime.causality and ordering to astra.temporal.causal. This
module adds NO new interval mathematics; it adds light-cone membership
semantics and observer-centric accessibility.

Scope: finite coordinate separations interpreted as local intervals
(exact for Minkowski, first-order for curved). Full null-geodesic tracing
for curved backgrounds is deferred to spacetime geodesics.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence, Tuple

from astra.spacetime.causality import classify_interval as spacetime_classify
from astra.spacetime.events import SpacetimeEvent, CHART_CARTESIAN
from astra.spacetime.metric import MetricField
from astra.temporal.causal import light_cone_region, is_causally_accessible, LightConeRegion
from astra.observation.exceptions import InvalidTargetError

class LightConeKind(str, Enum):
    PAST = "past"
    FUTURE = "future"

@dataclass(frozen=True)
class LightCone:
    """Immutable light-cone description.

    Attributes:
        apex: the apex event (ct,x,y,z)
        metric: the active metric used for classification
        kind: PAST (events that can reach apex) or FUTURE (apex can reach)
    """

    apex: SpacetimeEvent
    metric: MetricField
    kind: LightConeKind

    def contains(self, event: SpacetimeEvent, tolerance: float = 1e-9) -> LightConeRegion:
        """Region of event relative to apex via the active metric."""
        # Convert events to chart coordinate tuples (ct,x,y,z) for metric
        a = (self.apex.ct_m, self.apex.x, self.apex.y, self.apex.z)
        b = (event.ct_m, event.x, event.y, event.z)
        return light_cone_region(self.metric, a, b, tolerance)

    def is_inside_or_on(self, event: SpacetimeEvent, tolerance: float = 1e-9) -> bool:
        region = self.contains(event, tolerance)
        if self.kind == LightConeKind.PAST:
            return region in (LightConeRegion.INSIDE_PAST_CONE, LightConeRegion.ON_PAST_CONE)
        else:
            return region in (LightConeRegion.INSIDE_FUTURE_CONE, LightConeRegion.ON_FUTURE_CONE)

    def is_accessible(self, event: SpacetimeEvent, tolerance: float = 1e-9) -> bool:
        """Causal accessibility check.

        For PAST cone: event can reach apex (event in past).
        For FUTURE cone: apex can reach event (event in future).
        """
        a = (self.apex.ct_m, self.apex.x, self.apex.y, self.apex.z)
        b = (event.ct_m, event.x, event.y, event.z)
        if self.kind == LightConeKind.PAST:
            return is_causally_accessible(self.metric, b, a, tolerance)
        else:
            return is_causally_accessible(self.metric, a, b, tolerance)


def past_light_cone(observer_event: SpacetimeEvent, metric: MetricField) -> LightCone:
    if not isinstance(observer_event, SpacetimeEvent):
        raise InvalidTargetError("observer_event must be SpacetimeEvent")
    return LightCone(apex=observer_event, metric=metric, kind=LightConeKind.PAST)

def future_light_cone(source_event: SpacetimeEvent, metric: MetricField) -> LightCone:
    if not isinstance(source_event, SpacetimeEvent):
        raise InvalidTargetError("source_event must be SpacetimeEvent")
    return LightCone(apex=source_event, metric=metric, kind=LightConeKind.FUTURE)

def is_observable(
    source_event: SpacetimeEvent,
    observer_event: SpacetimeEvent,
    metric: MetricField,
    tolerance: float = 1e-9,
) -> bool:
    """True iff source_event is on or inside observer's past light cone."""
    cone = past_light_cone(observer_event, metric)
    return cone.is_inside_or_on(source_event, tolerance)

def observability_status(
    source_event: SpacetimeEvent,
    observer_event: SpacetimeEvent,
    metric: MetricField,
) -> str:
    """Human-readable observability:

    - 'observable' : past cone inside/on
    - 'not_yet_observable' : future cone (source in observer future)
    - 'causally_inaccessible' : spacelike exterior
    - 'coincident' : same event
    """
    a = (source_event.ct_m, source_event.x, source_event.y, source_event.z)
    b = (observer_event.ct_m, observer_event.x, observer_event.y, observer_event.z)
    # quick coincident
    if a==b:
        return "coincident"
    region = light_cone_region(metric, b, a)  # observer apex, source candidate
    if region in (LightConeRegion.INSIDE_PAST_CONE, LightConeRegion.ON_PAST_CONE):
        return "observable"
    if region in (LightConeRegion.INSIDE_FUTURE_CONE, LightConeRegion.ON_FUTURE_CONE):
        return "not_yet_observable"
    return "causally_inaccessible"

def causal_order_status(
    a: SpacetimeEvent,
    b: SpacetimeEvent,
    metric: MetricField,
) -> str:
    """Return causal relation label using temporal.causal.relate."""
    from astra.temporal.causal import relate
    ca=(a.ct_m, a.x, a.y, a.z)
    cb=(b.ct_m, b.x, b.y, b.z)
    rel = relate(metric, ca, cb)
    return rel.value
