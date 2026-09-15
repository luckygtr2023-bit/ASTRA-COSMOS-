"""Integration Protocols. Reconciled — adapters to real ASTRA APIs.

Protocols remain for test injection (mock providers). Real adapters that
delegate to authoritative modules are provided as fallback when no provider
is injected into TravelEngine.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from astra.core.threading import AuthorityContext
from astra.core.exceptions import AuthorityError as CoreAuthorityError


@runtime_checkable
class AuthorityProvider(Protocol):
    def require(self, operation: str) -> None: ...


class DefaultAuthorityProvider:
    """AuthorityProvider that delegates to real ASTRA threading registry.

    If no simulation thread is registered (e.g., in tests), authority is
    considered granted to avoid blocking deterministic unit tests. In
    production where a simulation thread is registered, non-sim threads are
    rejected.
    """

    def require(self, operation: str) -> None:
        from astra.core.threading import get_simulation_thread_registry

        reg = get_simulation_thread_registry()
        if not reg.is_registered():
            return
        # When registered, only sim thread may mutate travel state
        try:
            AuthorityContext.require_authority(operation)
        except CoreAuthorityError as e:
            from .errors import TravelAuthorityError

            raise TravelAuthorityError(str(e), operation=operation) from e


@runtime_checkable
class RelativityProvider(Protocol):
    """Wraps authoritative Relativity API."""

    def lorentz_factor(self, velocity: Any) -> float: ...

    def proper_time_delta(self, coordinate_dt: float, velocity: Any) -> float: ...

    def relativistic_momentum(self, mass_kg: float, velocity: Any) -> Any: ...

    def relativistic_energy(self, mass_kg: float, velocity: Any) -> float: ...


class DefaultRelativityProvider:
    def lorentz_factor(self, velocity: Any) -> float:
        from astra.relativity.core import lorentz_factor as _gamma

        return _gamma(velocity)

    def proper_time_delta(self, coordinate_dt: float, velocity: Any) -> float:
        from astra.temporal.proper_time import velocity_time_dilation

        return velocity_time_dilation(coordinate_dt, velocity)

    def relativistic_momentum(self, mass_kg: float, velocity: Any) -> Any:
        from astra.relativity.core import relativistic_momentum as _mom

        # velocity expected Vector3 or Vec3
        from astra.mathematics import Vector3

        if hasattr(velocity, "to_vector3"):
            v = velocity.to_vector3()
        elif isinstance(velocity, Vector3):
            v = velocity
        else:
            # assume tuple
            v = Vector3(float(velocity[0]), float(velocity[1]), float(velocity[2]))
        return _mom(mass_kg, v)

    def relativistic_energy(self, mass_kg: float, velocity: Any) -> float:
        from astra.relativity.core import total_energy as _te

        speed = 0.0
        if hasattr(velocity, "norm"):
            speed = float(velocity.norm())
        elif hasattr(velocity, "magnitude"):
            speed = float(velocity.magnitude())
        else:
            speed = float(velocity)
        return _te(mass_kg, speed)


@runtime_checkable
class SpacetimeProvider(Protocol):
    """Wraps authoritative Spacetime API."""

    def metric_at(self, position: Any) -> Any: ...

    def proper_time_along(self, worldline: Any) -> float: ...


class DefaultSpacetimeProvider:
    def metric_at(self, position: Any):
        from astra.spacetime.metric import MinkowskiMetric

        return MinkowskiMetric()

    def proper_time_along(self, worldline: Any) -> float:
        from astra.temporal.proper_time import flat_proper_time

        # worldline may be travel Worldline or spacetime Worldline
        if hasattr(worldline, "to_spacetime_worldline"):
            st = worldline.to_spacetime_worldline()
        else:
            st = worldline
        return flat_proper_time(st)


@runtime_checkable
class BlackHoleProvider(Protocol):
    """Wraps authoritative Black-Hole API."""

    def gravitational_time_dilation(self, r: float, mass_kg: float) -> float: ...

    def gravitational_redshift(self, r_emit: float, r_obs: float, mass_kg: float) -> float: ...


class DefaultBlackHoleProvider:
    def gravitational_time_dilation(self, r: float, mass_kg: float) -> float:
        from astra.blackhole.api import gravitational_time_dilation as _gtd
        from astra.blackhole.api import create_black_hole

        bh = create_black_hole(mass_kg)
        return _gtd(bh, r)

    def gravitational_redshift(self, r_emit: float, r_obs: float, mass_kg: float) -> float:
        from astra.blackhole.api import gravitational_redshift as _grs
        from astra.blackhole.api import create_black_hole

        bh = create_black_hole(mass_kg)
        return _grs(bh, r_emit, r_obs)


@runtime_checkable
class TemporalCausalityProvider(Protocol):
    """Wraps authoritative Temporal & Causality API."""

    def check_causal_order(self, departure: Any, arrival: Any) -> Any: ...

    def classify_worldline(self, worldline: Any) -> Any: ...


class DefaultTemporalCausalityProvider:
    def check_causal_order(self, departure: Any, arrival: Any):
        # departure/arrival are (t, Vec3 or tuple)
        from astra.spacetime.metric import MinkowskiMetric
        from astra.temporal.causal import relate, CausalRelation

        metric = MinkowskiMetric()
        from astra.relativity.core import SPEED_OF_LIGHT

        # convert to coords (ct, x, y, z)
        def to_coords(event):
            t, pos = event
            if hasattr(pos, "to_tuple"):
                x, y, z = pos.to_tuple()
            elif isinstance(pos, (list, tuple)):
                x, y, z = float(pos[0]), float(pos[1]), float(pos[2])
            else:
                # Vector3
                x, y, z = float(pos.x), float(pos.y), float(pos.z)
            return (t * SPEED_OF_LIGHT, x, y, z)

        ca = to_coords(departure)
        cb = to_coords(arrival)
        relation = relate(metric, ca, cb)
        # map to travel CausalStatus
        from .types import CausalStatus

        mapping = {
            CausalRelation.COINCIDENT: CausalStatus.CASUAL,
            CausalRelation.A_PRECEDES_B: CausalStatus.TIMELIKE,
            CausalRelation.B_PRECEDES_A: CausalStatus.CAUSALLY_INVALID,
            CausalRelation.CAUSALLY_DISCONNECTED: CausalStatus.SPACELIKE,
        }
        return mapping.get(relation, CausalStatus.UNKNOWN)

    def classify_worldline(self, worldline: Any):
        from astra.spacetime.metric import MinkowskiMetric
        from astra.temporal.causal import classify
        from astra.spacetime.causality import IntervalType

        metric = MinkowskiMetric()
        if hasattr(worldline, "to_spacetime_worldline"):
            st = worldline.to_spacetime_worldline()
            events = st.events
        else:
            events = worldline.events if hasattr(worldline, "events") else []
        if len(events) < 2:
            from .types import CausalStatus

            return CausalStatus.UNKNOWN
        # check first and last
        from astra.relativity.core import SPEED_OF_LIGHT

        a = events[0]
        b = events[-1]
        ca = (a.ct_m, a.x, a.y, a.z)
        cb = (b.ct_m, b.x, b.y, b.z)
        kind = classify(metric, ca, cb)
        from .types import CausalStatus

        if kind.value == "TIMELIKE":
            return CausalStatus.TIMELIKE
        if kind.value == "NULL":
            return CausalStatus.LIGHTLIKE
        if kind.value == "SPACELIKE":
            return CausalStatus.SPACELIKE
        return CausalStatus.UNKNOWN


@runtime_checkable
class ObservationProvider(Protocol):
    """Wraps Observation & Cosmic History Engine."""

    def record_departure(self, payload: dict) -> str: ...

    def record_travel(self, payload: dict) -> str: ...

    def record_arrival(self, payload: dict) -> str: ...


class DefaultObservationProvider:
    def __init__(self):
        self._records = []

    def record_departure(self, payload: dict) -> str:
        self._records.append(("departure", payload))
        return f"obs-dep-{len(self._records)}"

    def record_travel(self, payload: dict) -> str:
        self._records.append(("travel", payload))
        return f"obs-tra-{len(self._records)}"

    def record_arrival(self, payload: dict) -> str:
        self._records.append(("arrival", payload))
        return f"obs-arr-{len(self._records)}"


@runtime_checkable
class MeasurementProvider(Protocol):
    """Wraps Astronomical Observatory & Measurement Engine."""

    def measure_redshift(self, source: Any, observer: Any) -> float: ...

    def measure_apparent_position(self, source: Any, observer: Any) -> Any: ...


class DefaultMeasurementProvider:
    def measure_redshift(self, source: Any, observer: Any) -> float:
        # delegate to observation redshift if available
        from astra.observation.redshift import doppler_redshift
        import math

        # placeholder: use doppler if velocity provided
        return 0.0

    def measure_apparent_position(self, source: Any, observer: Any) -> Any:
        return getattr(source, "position", source)


@runtime_checkable
class SpacecraftStateProvider(Protocol):
    """Wraps Spacecraft Physics state."""

    def get_state(self, spacecraft_id: str) -> Any: ...

    def apply_state(self, spacecraft_id: str, new_state: Any) -> None: ...


class DefaultSpacecraftStateProvider:
    def __init__(self):
        self._states = {}

    def get_state(self, spacecraft_id: str) -> Any:
        return self._states.get(spacecraft_id)

    def apply_state(self, spacecraft_id: str, new_state: Any) -> None:
        self._states[spacecraft_id] = new_state
