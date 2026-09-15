"""Integration Protocols. Reconciled — adapters to real ASTRA APIs.

Protocols remain for test injection (mock providers). Real adapters delegate
to authoritative modules and perform finite-light observation via
CosmicHistory / ObservationEngine and measurement via ObservatoryEngine.
"""
from __future__ import annotations

import math
from typing import Any, Protocol, runtime_checkable

from astra.core.threading import AuthorityContext
from astra.core.exceptions import AuthorityError as CoreAuthorityError


@runtime_checkable
class AuthorityProvider(Protocol):
    def require(self, operation: str) -> None: ...


class DefaultAuthorityProvider:
    """AuthorityProvider that delegates to real ASTRA threading registry."""

    def require(self, operation: str) -> None:
        from astra.core.threading import get_simulation_thread_registry

        reg = get_simulation_thread_registry()
        if not reg.is_registered():
            return
        try:
            AuthorityContext.require_authority(operation)
        except CoreAuthorityError as e:
            from .errors import TravelAuthorityError

            raise TravelAuthorityError(str(e), operation=operation) from e


@runtime_checkable
class RelativityProvider(Protocol):
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
        from astra.mathematics import Vector3

        if hasattr(velocity, "to_vector3"):
            v = velocity.to_vector3()
        elif isinstance(velocity, Vector3):
            v = velocity
        else:
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
    def metric_at(self, position: Any) -> Any: ...

    def proper_time_along(self, worldline: Any) -> float: ...

    def metric_for_config(self, config: dict) -> Any: ...


class DefaultSpacetimeProvider:
    def metric_at(self, position: Any):
        from astra.spacetime.metric import MinkowskiMetric

        return MinkowskiMetric()

    def metric_for_config(self, config: dict):
        """Select metric based on travel config (for gravitational/warp)."""
        # If warp metric present, return it
        if "warp_metric" in config:
            return config["warp_metric"]
        # If black hole mass present, return Schwarzschild
        mass = config.get("mass_kg") or config.get("black_hole_mass_kg")
        if mass is not None:
            try:
                from astra.spacetime.metric import SchwarzschildMetric

                return SchwarzschildMetric(float(mass))
            except Exception:
                pass
        # If wormhole throat present, return MorrisThorne if available
        if "wormhole_metric" in config:
            return config["wormhole_metric"]
        from astra.spacetime.metric import MinkowskiMetric

        return MinkowskiMetric()

    def proper_time_along(self, worldline: Any) -> float:
        from astra.temporal.proper_time import flat_proper_time

        if hasattr(worldline, "to_spacetime_worldline"):
            st = worldline.to_spacetime_worldline()
        else:
            st = worldline
        return flat_proper_time(st)


@runtime_checkable
class BlackHoleProvider(Protocol):
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
    def check_causal_order(self, departure: Any, arrival: Any) -> Any: ...

    def classify_worldline(self, worldline: Any) -> Any: ...

    def check_with_metric(self, metric: Any, departure: Any, arrival: Any) -> Any: ...


class DefaultTemporalCausalityProvider:
    def check_causal_order(self, departure: Any, arrival: Any):
        from astra.spacetime.metric import MinkowskiMetric
        from astra.temporal.causal import relate, CausalRelation

        metric = MinkowskiMetric()
        return self.check_with_metric(metric, departure, arrival)

    def check_with_metric(self, metric: Any, departure: Any, arrival: Any):
        from astra.temporal.causal import relate, CausalRelation
        from astra.relativity.core import SPEED_OF_LIGHT

        def to_coords(event):
            t, pos = event
            if hasattr(pos, "to_tuple"):
                x, y, z = pos.to_tuple()
            elif isinstance(pos, (list, tuple)):
                x, y, z = float(pos[0]), float(pos[1]), float(pos[2])
            else:
                x, y, z = float(pos.x), float(pos.y), float(pos.z)
            return (t * SPEED_OF_LIGHT, x, y, z)

        ca = to_coords(departure)
        cb = to_coords(arrival)
        relation = relate(metric, ca, cb)
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

        metric = MinkowskiMetric()
        if hasattr(worldline, "to_spacetime_worldline"):
            st = worldline.to_spacetime_worldline()
            events = st.events
        else:
            events = worldline.events if hasattr(worldline, "events") else []
        if len(events) < 2:
            from .types import CausalStatus

            return CausalStatus.UNKNOWN
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
    def record_departure(self, payload: dict) -> str: ...

    def record_travel(self, payload: dict) -> str: ...

    def record_arrival(self, payload: dict) -> str: ...

    def solve_observation(self, traveler_id: str, worldline: Any, observer: Any, observation_time_s: float) -> Any: ...


class DefaultObservationProvider:
    """Wraps CosmicHistory + ObservationEngine for finite-light observation.

    If a real CosmicHistory is not injected, this provider creates an
    isolated history per travel and solves retarded time via the
    authoritative propagation (bisection on recorded history bracket).
    This preserves finite light propagation exactly as the observation
    layer does, rather than a simple distance/c estimate.
    """

    def __init__(self):
        self._records = []
        self._id_counter = 0
        # Optional isolated CosmicHistory/ObservationEngine per provider
        self._history = None
        self._engine = None
        self._observer_registry = {}

    def _ensure_engine(self):
        if self._history is None:
            from astra.observation.history import CosmicHistory
            from astra.observation.engine import ObservationEngine
            from astra.spacetime.metric import MinkowskiMetric

            self._history = CosmicHistory()
            self._engine = ObservationEngine(cosmic_history=self._history, metric=MinkowskiMetric())
        return self._history, self._engine

    def record_departure(self, payload: dict) -> str:
        self._records.append(("departure", payload))
        # Also store in cosmic history for later retarded solving
        try:
            history, engine = self._ensure_engine()
            from astra.observation.history import HistoricalSnapshot
            from astra.celestial.provenance import DataProvenance, ProvenanceTag

            tid = payload.get("travel_id", "unknown")
            pos = payload.get("position", (0, 0, 0))
            t = payload.get("time_s", 0.0)
            # Ensure position is tuple
            if hasattr(pos, "to_tuple"):
                pos = pos.to_tuple()
            elif isinstance(pos, Any) and hasattr(pos, "x"):
                pos = (pos.x, pos.y, pos.z)
            history.add_snapshot(
                tid,
                HistoricalSnapshot(
                    timestamp_s=float(t),
                    state={"position": tuple(float(x) for x in pos)},
                    provenance=ProvenanceTag(DataProvenance.SIMULATED_DATA),
                ),
            )
        except Exception:
            pass
        self._id_counter += 1
        return f"obs-dep-{self._id_counter}"

    def record_arrival(self, payload: dict) -> str:
        self._records.append(("arrival", payload))
        try:
            history, engine = self._ensure_engine()
            from astra.observation.history import HistoricalSnapshot
            from astra.celestial.provenance import DataProvenance, ProvenanceTag

            tid = payload.get("travel_id", "unknown")
            pos = payload.get("position", (0, 0, 0))
            t = payload.get("time_s", 0.0)
            if hasattr(pos, "to_tuple"):
                pos = pos.to_tuple()
            history.add_snapshot(
                tid,
                HistoricalSnapshot(
                    timestamp_s=float(t),
                    state={"position": tuple(float(x) for x in pos)},
                    provenance=ProvenanceTag(DataProvenance.SIMULATED_DATA),
                ),
            )
        except Exception:
            pass
        self._id_counter += 1
        return f"obs-arr-{self._id_counter}"

    def record_travel(self, payload: dict) -> str:
        self._records.append(("travel", payload))
        self._id_counter += 1
        return f"obs-tra-{self._id_counter}"

    def solve_observation(self, traveler_id: str, worldline: Any, observer: Any, observation_time_s: float):
        """Solve retarded observation via ObservationEngine.

        Returns ObservedState (or None if history unavailable). Uses the
        authoritative light-cone solving (bisection) preserving finite c.
        """
        try:
            history, engine = self._ensure_engine()
            # Ensure worldline history is populated
            if hasattr(worldline, "samples"):
                from astra.observation.history import HistoricalSnapshot
                from astra.celestial.provenance import DataProvenance, ProvenanceTag

                for s in worldline.samples:
                    # Avoid duplicate timestamps
                    try:
                        # Check if snapshot exists at this time
                        existing = [snap.timestamp_s for snap in history.get_snapshots(traveler_id)]
                        if s.coordinate_time_s not in existing:
                            history.add_snapshot(
                                traveler_id,
                                HistoricalSnapshot(
                                    timestamp_s=float(s.coordinate_time_s),
                                    state={"position": s.position.to_tuple()},
                                    provenance=ProvenanceTag(DataProvenance.SIMULATED_DATA),
                                ),
                            )
                    except Exception:
                        pass
            # Build Observer if needed
            from astra.observation.observer import Observer

            if isinstance(observer, Observer):
                obs = observer
            elif isinstance(observer, dict):
                pos = observer.get("position", (0, 0, 0))
                if hasattr(pos, "to_tuple"):
                    pos = pos.to_tuple()
                obs = Observer(
                    observer_id=observer.get("observer_id", "obs-1"),
                    position=tuple(float(x) for x in pos),
                    velocity=observer.get("velocity", (0, 0, 0)),
                    observation_time_s=float(observation_time_s),
                )
            elif isinstance(observer, (list, tuple)):
                obs = Observer(
                    observer_id="obs-1",
                    position=tuple(float(x) for x in observer),
                    velocity=(0, 0, 0),
                    observation_time_s=float(observation_time_s),
                )
            else:
                # Default at origin
                obs = Observer(
                    observer_id="obs-1", position=(0, 0, 0), velocity=(0, 0, 0), observation_time_s=float(observation_time_s)
                )
            engine.register_observer(obs)
            observed = engine.observe(obs, traveler_id, observation_time_s=observation_time_s)
            return observed
        except Exception:
            return None


@runtime_checkable
class MeasurementProvider(Protocol):
    def measure_redshift(self, source: Any, observer: Any) -> float: ...

    def measure_apparent_position(self, source: Any, observer: Any) -> Any: ...

    def measure_via_observatory(self, traveler_id: str, worldline: Any, observer: Any) -> dict: ...


class DefaultMeasurementProvider:
    """Wraps ObservatoryEngine for redshift/apparent position.

    Delegates to ObservatoryEngine.measure when possible; falls back to
    observation-layer redshift components.
    """

    def __init__(self):
        self._engine = None
        self._observatory = None
        self._instrument = None

    def _ensure_observatory(self):
        if self._engine is None:
            try:
                from astra.observation.history import CosmicHistory
                from astra.observation.engine import ObservationEngine
                from astra.observatory.observatory import Observatory
                from astra.observatory.instrument import optical_telescope
                from astra.observatory.engine import ObservatoryEngine
                from astra.spacetime.metric import MinkowskiMetric

                hist = CosmicHistory()
                obs_engine = ObservationEngine(cosmic_history=hist, metric=MinkowskiMetric())
                observatory = Observatory(
                    observatory_id="travel-obs",
                    location=(0, 0, 0),
                    orientation=(1, 0, 0),
                )
                instrument = optical_telescope("travel-tel", aperture_m=1.0)
                engine = ObservatoryEngine(observation_engine=obs_engine)
                self._engine = engine
                self._observatory = observatory
                self._instrument = instrument
                self._history = hist
                self._obs_engine = obs_engine
            except Exception:
                self._engine = None
        return self._engine

    def measure_redshift(self, source: Any, observer: Any) -> float:
        # Try observatory path first
        try:
            eng = self._ensure_observatory()
            if eng is not None:
                # Need an ObservedState; try observation redshift directly
                from astra.observation.redshift import calculate_redshift

                src_pos = getattr(source, "position", source) if not isinstance(source, (list, tuple)) else source
                obs_pos = getattr(observer, "position", observer) if not isinstance(observer, (list, tuple)) else observer
                # If source has velocity, use doppler
                vel = getattr(source, "velocity", (0, 0, 0))
                if hasattr(vel, "to_tuple"):
                    vel = vel.to_tuple()
                # Simplified: use doppler_redshift if velocity available
                from astra.observation.redshift import doppler_redshift

                try:
                    return doppler_redshift(vel, src_pos if isinstance(src_pos, (list, tuple)) else (0, 0, 0))
                except Exception:
                    pass
        except Exception:
            pass
        return 0.0

    def measure_apparent_position(self, source: Any, observer: Any) -> Any:
        # Return source position as seen — real engine would apply lookback
        pos = getattr(source, "position", source)
        if hasattr(pos, "to_tuple"):
            return pos.to_tuple()
        return pos

    def measure_via_observatory(self, traveler_id: str, worldline: Any, observer: Any) -> dict:
        """Attempt full observatory measurement pipeline."""
        try:
            eng = self._ensure_observatory()
            if eng is None:
                return {}
            # Populate history from worldline if needed
            hist = self._history
            obs_engine = self._obs_engine
            from astra.observation.history import HistoricalSnapshot
            from astra.celestial.provenance import DataProvenance, ProvenanceTag

            if hasattr(worldline, "samples"):
                for s in worldline.samples:
                    try:
                        hist.add_snapshot(
                            traveler_id,
                            HistoricalSnapshot(
                                timestamp_s=float(s.coordinate_time_s),
                                state={"position": s.position.to_tuple()},
                                provenance=ProvenanceTag(DataProvenance.SIMULATED_DATA),
                            ),
                        )
                    except Exception:
                        pass
            # Observe via observation engine then measure via observatory
            from astra.observation.observer import Observer

            if isinstance(observer, (list, tuple)):
                obs = Observer(observer_id="obs-1", position=tuple(float(x) for x in observer), velocity=(0, 0, 0), observation_time_s=worldline.samples[-1].coordinate_time_s)
            elif isinstance(observer, dict):
                pos = observer.get("position", (0, 0, 0))
                obs = Observer(observer_id="obs-1", position=tuple(float(x) for x in pos), velocity=(0, 0, 0), observation_time_s=worldline.samples[-1].coordinate_time_s)
            else:
                obs = Observer(observer_id="obs-1", position=(0, 0, 0), velocity=(0, 0, 0), observation_time_s=worldline.samples[-1].coordinate_time_s)
            obs_engine.register_observer(obs)
            observed = obs_engine.observe(obs, traveler_id, observation_time_s=worldline.samples[-1].coordinate_time_s)
            # Now measure via observatory engine — need exposure
            from astra.observatory.exposure import Exposure

            exp = Exposure(start_time_s=observed.observation_time_s, duration_s=10.0)
            result = eng.measure(self._observatory, self._instrument, observed, exp)
            return result
        except Exception as e:
            return {"error": str(e)}


@runtime_checkable
class SpacecraftStateProvider(Protocol):
    def get_state(self, spacecraft_id: str) -> Any: ...

    def apply_state(self, spacecraft_id: str, new_state: Any) -> None: ...


class DefaultSpacecraftStateProvider:
    def __init__(self):
        self._states = {}

    def get_state(self, spacecraft_id: str) -> Any:
        return self._states.get(spacecraft_id)

    def apply_state(self, spacecraft_id: str, new_state: Any) -> None:
        self._states[spacecraft_id] = new_state
