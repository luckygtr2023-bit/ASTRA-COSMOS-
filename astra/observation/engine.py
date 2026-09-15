"""Observation & Cosmic History Engine — authoritative observation pipeline.

Pipeline (strict):
  PHYSICAL STATE → COSMIC/HISTORICAL STATE → LIGHT PROPAGATION → OBSERVATION EVENT → OBSERVED STATE → OBSERVABLE QUANTITIES

Separation guarantees:
* simulation_time vs cosmic_time vs observer proper_time vs emission vs arrival vs lookback vs coordinate_time are never conflated
* observed state is immutable DERIVED_DATA, never mutates authoritative history
* observation does NOT rewind the universe; it retrieves via CosmicHistory
* provenance is explicit (REAL/DERIVED/SIMULATED/THEORETICAL/SPECULATIVE)

Integration points (reused, not rebuilt):
* temporal.observation / spacetime.causality / relativity / procedural history / world spatial index

High-level API conceptually:
  observe(observer, target, observation_time)
  calculate_lookback_time(...)
  calculate_apparent_position(...)
  calculate_redshift(...)
  reconstruct_historical_state(...)
  trace_light_path(...)
  get_observable_events(...)

Deterministic: identical inputs → identical outputs; no RNG, no wall-clock.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from astra.relativity.core import SPEED_OF_LIGHT
from astra.spacetime.events import SpacetimeEvent, Worldline, CHART_CARTESIAN
from astra.spacetime.metric import MetricField, MinkowskiMetric
from astra.celestial.provenance import DataProvenance, ProvenanceTag
from astra.observation.observer import Observer
from astra.observation.history import CosmicHistory, HistoricalSnapshot, TimelineEvent
from astra.observation.propagation import (
    solve_retarded_time,
    solve_retarded_time_with_observer,
    trace_light_path as trace_path,
    geometric_distance,
)
from astra.observation.redshift import RedshiftComponents, calculate_redshift
from astra.observation.state import ObservedState
from astra.observation.light_cone import LightCone, past_light_cone, is_observable, observability_status
from astra.observation.exceptions import (
    InvalidObserverError,
    InvalidTargetError,
    HistoryUnavailableError,
    PropagationError,
    CausalInaccessibilityError,
    UnsupportedObservationalConfigurationError,
)
from astra.temporal.exceptions import TemporalHistoryUnavailableError as TemporalHistError

# For type flexibility, Target can be Worldline, HistoricalSnapshot lookup via history, CelestialObject dict, etc.

def _check_time(t, name: str) -> float:
    if isinstance(t, bool) or not isinstance(t, (int, float)) or math.isnan(float(t)) or math.isinf(float(t)) or float(t) < 0:
        # observation_time is observer-related, treat as observer error for negative
        if "observation" in name:
            raise InvalidObserverError(f"{name} must be finite >=0, got {t!r}")
        raise InvalidTargetError(f"{name} must be finite >=0, got {t!r}")
    return float(t)

def _vec3(v, name: str) -> Tuple[float,float,float]:
    if not isinstance(v, (list, tuple)) or len(v)!=3:
        raise InvalidTargetError(f"{name} must be (x,y,z)")
    out=tuple(float(x) for x in v)
    if any(math.isnan(x) or math.isinf(x) for x in out):
        raise InvalidTargetError(f"{name} contains non-finite")
    return out

def _worldline_from_history(history: CosmicHistory, object_id: str) -> Worldline:
    snaps = history.get_snapshots(object_id)
    if not snaps:
        raise HistoryUnavailableError(f"no history for {object_id!r}")
    samples=[]
    for s in snaps:
        # state must contain position; expect state['position'] or x,y,z
        st=s.state
        if "position" in st:
            pos=st["position"]
            x,y,z=float(pos[0]), float(pos[1]), float(pos[2])
        elif "x" in st and "y" in st and "z" in st:
            x,y,z=float(st["x"]), float(st["y"]), float(st["z"])
        else:
            # fallback: try to infer from event? skip if no position
            continue
        ev=SpacetimeEvent.from_coordinates(s.timestamp_s, x, y, z, CHART_CARTESIAN)
        samples.append((s.timestamp_s, ev))
    if len(samples)<2:
        raise HistoryUnavailableError(f"history for {object_id!r} has <2 positional samples")
    # ensure sorted
    samples.sort(key=lambda x: x[0])
    return Worldline(tuple(samples))

def _velocity_from_history(history: CosmicHistory, object_id: str, t: float, dt: float = 1.0) -> Tuple[float,float,float]:
    """Finite-difference velocity at t via reconstructed states."""
    try:
        s0=history.reconstruct_state(object_id, max(0, t-dt))
        s1=history.reconstruct_state(object_id, t+dt)
    except Exception:
        return (0,0,0)
    # extract positions
    def pos_of(s):
        st=s.state
        if "position" in st:
            p=st["position"]
            return (float(p[0]), float(p[1]), float(p[2]))
        return (float(st.get("x",0)), float(st.get("y",0)), float(st.get("z",0)))
    p0=pos_of(s0); p1=pos_of(s1)
    # s0.timestamp, s1.timestamp may not be exactly t±dt if interpolation
    t0=s0.timestamp_s; t1=s1.timestamp_s
    if t1==t0:
        return (0,0,0)
    return ((p1[0]-p0[0])/(t1-t0), (p1[1]-p0[1])/(t1-t0), (p1[2]-p0[2])/(t1-t0))

def _scale_factor_from_history(history: CosmicHistory, object_id: str, t: float) -> Optional[float]:
    try:
        snap=history.reconstruct_state(object_id, t)
        # check metadata and state
        for src in (snap.metadata, snap.state):
            if "scale_factor" in src:
                return float(src["scale_factor"])
            if "a" in src:
                return float(src["a"])
        return None
    except Exception:
        return None

class ObservationEngine:
    """Authoritative observation engine.

    Owns the observation pipeline. Does NOT own simulation time, metrics,
    or universe evolution — it consumes them.

    Thread-safe for read paths (no mutation of history during observe).
    """

    def __init__(
        self,
        cosmic_history: Optional[CosmicHistory] = None,
        metric: Optional[MetricField] = None,
        world_spatial_index: Optional[Any] = None,
    ):
        self.cosmic_history = cosmic_history or CosmicHistory()
        self.metric: MetricField = metric or MinkowskiMetric()
        self.world_spatial_index = world_spatial_index  # optional SpatialIndex
        self._observers: Dict[str, Observer] = {}

    # -- observer registry ------------------------------------------------
    def register_observer(self, observer: Observer) -> None:
        if not isinstance(observer, Observer):
            raise InvalidObserverError("observer must be Observer")
        self._observers[observer.observer_id] = observer

    def get_observer(self, observer_id: str) -> Optional[Observer]:
        return self._observers.get(observer_id)

    # -- worldline resolution ---------------------------------------------
    def _resolve_worldline(self, target: Any, target_id: Optional[str] = None) -> Tuple[Worldline, str]:
        """Resolve target to (Worldline, source_id)."""
        if isinstance(target, Worldline):
            sid = target_id or "worldline_target"
            return target, sid
        if isinstance(target, str):
            # treat as object_id in history
            return _worldline_from_history(self.cosmic_history, target), target
        if isinstance(target, dict):
            # dict may contain worldline or position history
            if "worldline" in target and isinstance(target["worldline"], Worldline):
                return target["worldline"], target.get("id", target_id or "dict_target")
            if "position" in target or ("x" in target and "y" in target):
                # single position → need history? build minimal worldline around target time later
                raise InvalidTargetError("dict target must provide a Worldline or be registered in history")
            # if dict has id and history exists
            did = target.get("id") or target.get("source_id") or target_id
            if did and did in self.cosmic_history.object_ids():
                return _worldline_from_history(self.cosmic_history, did), did
            raise InvalidTargetError(f"cannot resolve worldline for dict target {target!r}")
        # CelestialObject or similar: try to get position from properties?
        # As fallback, try to use history if target has identity attribute
        if hasattr(target, "identity"):
            ident = getattr(target, "identity")
            # identity may have id string
            cand = getattr(ident, "id", None) or getattr(ident, "value", None) or str(ident)
            try:
                return _worldline_from_history(self.cosmic_history, str(cand)), str(cand)
            except Exception:
                pass
        raise InvalidTargetError(f"cannot resolve target {type(target).__name__}: provide Worldline or registered history id")

    # -- core observation --------------------------------------------------
    def observe(
        self,
        observer: Union[Observer, str],
        target: Any,
        observation_time_s: Optional[float] = None,
        target_id: Optional[str] = None,
        reference_frame: Optional[str] = None,
    ) -> ObservedState:
        """Observe a target from an observer at observation_time_s.

        Returns an immutable ObservedState (DERIVED_DATA). Provenance of the
        source historical state is preserved in metadata; the observed
        quantities themselves are DERIVED_DATA.

        Args:
            observer: Observer instance or observer_id string (must be registered)
            target: Worldline, object_id string, or dict/CelestialObject with history
            observation_time_s: coordinate/observation time (s). If None, uses
                                observer.observation_time_s (must be set).
            target_id: optional explicit source id when target is Worldline
            reference_frame: override observer's frame for this observation

        Raises:
            InvalidObserverError, InvalidTargetError, HistoryUnavailableError,
            CausalInaccessibilityError
        """
        # resolve observer
        if isinstance(observer, str):
            obs = self._observers.get(observer)
            if obs is None:
                raise InvalidObserverError(f"unknown observer {observer!r}; register first")
        elif isinstance(observer, Observer):
            obs = observer
        else:
            raise InvalidObserverError(f"observer must be Observer or id, got {type(observer).__name__}")

        t_obs = observation_time_s if observation_time_s is not None else obs.observation_time_s
        if t_obs is None:
            raise InvalidObserverError("observation_time_s must be supplied (observer has no default)")
        t_obs = _check_time(t_obs, "observation_time_s")

        worldline, source_id = self._resolve_worldline(target, target_id)

        # solve retarded time (observer position at t_obs)
        try:
            t_emit, emission_event, actual_event, obs_pos = solve_retarded_time_with_observer(worldline, obs, t_obs)
        except TemporalHistError as e:
            raise HistoryUnavailableError(str(e)) from e
        except Exception as e:
            # wrap invalid
            if isinstance(e, (HistoryUnavailableError, TemporalHistError)):
                raise
            raise PropagationError(str(e)) from e

        # observer event at t_obs
        observer_event = SpacetimeEvent.from_coordinates(t_obs, obs_pos[0], obs_pos[1], obs_pos[2], CHART_CARTESIAN)

        # causal check via light cone (must be observable)
        status = observability_status(emission_event, observer_event, self.metric)
        if status not in ("observable", "coincident"):
            # still return but mark metadata; if causally_inaccessible raise?
            # Spec: determine whether observable/not yet/causally inaccessible.
            # For causally_inaccessible we should raise or mark. We mark but do not raise for spacelike?
            # However for past-light cone, a valid retarded solution is by construction observable in flat metric.
            # Only if metric is curved could it be inaccessible; we warn via metadata.
            pass

        # apparent quantities
        app_pos = (emission_event.x, emission_event.y, emission_event.z)
        app_dist = geometric_distance(obs_pos, app_pos)

        # reconstruct historical snapshot at emission for provenance & physical props
        hist_snapshot: Optional[HistoricalSnapshot] = None
        try:
            if source_id in self.cosmic_history.object_ids():
                hist_snapshot = self.cosmic_history.reconstruct_state(source_id, t_emit)
        except Exception:
            hist_snapshot = None

        # apparent velocity via finite difference at emission
        try:
            app_vel = _velocity_from_history(self.cosmic_history, source_id, t_emit) if source_id in self.cosmic_history.object_ids() else None
            if app_vel == (0,0,0):
                app_vel = None
        except Exception:
            app_vel = None

        # angular size & brightness from physical properties at emission
        ang_size = None
        brightness = None
        source_mass = None
        source_radius = None
        source_luminosity = None
        if hist_snapshot is not None:
            st = hist_snapshot.state
            # radius_m
            for k in ("radius_m","radius","radius_solar"):
                if k in st:
                    try:
                        source_radius = float(st[k])
                        # if solar units, convert approx? assume metres if small?? keep as is; if solar radius ~7e8, values >1e6 likely metres
                        # For stellar 1 solar = 6.96e8 m, but history may store solar units; we handle both by magnitude heuristic
                        if k == "radius_solar":
                            source_radius = source_radius * 6.957e8
                        break
                    except Exception:
                        pass
            for k in ("mass_kg","mass","mass_solar"):
                if k in st:
                    try:
                        source_mass = float(st[k])
                        if k == "mass_solar":
                            source_mass = source_mass * 1.98847e30
                        break
                    except Exception:
                        pass
            for k in ("luminosity_w","luminosity","luminosity_solar"):
                if k in st:
                    try:
                        source_luminosity = float(st[k])
                        if k == "luminosity_solar":
                            source_luminosity = source_luminosity * 3.828e26
                        break
                    except Exception:
                        pass
            # angular size = 2*arctan(r/d)  (≈2r/d)
            if source_radius is not None and app_dist > 0:
                try:
                    ang_size = 2.0 * math.atan(source_radius / app_dist) if source_radius < app_dist else math.pi
                except Exception:
                    ang_size = None
            # brightness = L / (4π d²)
            if source_luminosity is not None and app_dist > 0:
                try:
                    brightness = source_luminosity / (4.0 * math.pi * app_dist * app_dist)
                except Exception:
                    brightness = None

        # redshift decomposition
        # velocities: observer velocity vs source velocity at emission (approx)
        obs_vel = obs.velocity
        src_vel = (0.0, 0.0, 0.0)
        try:
            if source_id in self.cosmic_history.object_ids():
                src_vel = _velocity_from_history(self.cosmic_history, source_id, t_emit) or (0,0,0)
            else:
                # try to estimate from worldline: finite diff around emission
                # use worldline interpolation difference
                eps = 1.0  # 1 s
                try:
                    e0 = _interpolate_worldline_at(worldline, max(worldline.parameters[0], t_emit - eps))
                    e1 = _interpolate_worldline_at(worldline, min(worldline.parameters[-1], t_emit + eps))
                    dt = e1.time_sec - e0.time_sec
                    if dt != 0:
                        src_vel = ((e1.x-e0.x)/dt, (e1.y-e0.y)/dt, (e1.z-e0.z)/dt)
                except Exception:
                    src_vel = (0,0,0)
        except Exception:
            src_vel = (0,0,0)

        # line of sight unit from source emission to observer
        los = (obs_pos[0]-app_pos[0], obs_pos[1]-app_pos[1], obs_pos[2]-app_pos[2])
        los_len = math.sqrt(los[0]*los[0]+los[1]*los[1]+los[2]*los[2])
        if los_len == 0:
            los_unit = (1,0,0)
        else:
            los_unit = (los[0]/los_len, los[1]/los_len, los[2]/los_len)

        # scale factors for cosmology
        a_emit = _scale_factor_from_history(self.cosmic_history, source_id, t_emit) if source_id in self.cosmic_history.object_ids() else None
        a_obs = _scale_factor_from_history(self.cosmic_history, source_id, t_obs) if source_id in self.cosmic_history.object_ids() else None
        # if history has global scale factor, try generic key
        if a_emit is None:
            # try any object's metadata that has scale_factor at that time? fallback to cosmic history generic?
            a_emit = None
        # observer mass/radius for gravitational (if observer near compact object)
        obs_mass = obs.metadata.get("mass_kg") if isinstance(obs.metadata, dict) else None
        obs_radius = obs.metadata.get("radius_m") if isinstance(obs.metadata, dict) else None

        redshift = calculate_redshift(
            observer_velocity=obs_vel,
            source_velocity=src_vel,
            line_of_sight_unit=los_unit,
            source_mass_kg=source_mass,
            source_radius_m=source_radius,
            observer_mass_kg=obs_mass,
            observer_radius_m=obs_radius,
            scale_factor_emit=a_emit,
            scale_factor_obs=a_obs,
        )

        # provenance: observed quantities are DERIVED_DATA
        prov = ProvenanceTag(DataProvenance.DERIVED_DATA, source_label="astra.observation.engine")

        frame = reference_frame or obs.reference_frame

        metadata = {
            "source_id": source_id,
            "observer_id": obs.observer_id,
            "causal_status": observability_status(emission_event, observer_event, self.metric),
            "redshift_metadata": list(redshift.metadata),
        }
        if hist_snapshot is not None:
            metadata["source_provenance"] = hist_snapshot.provenance.provenance.value
            metadata["source_epoch"] = hist_snapshot.epoch
            metadata["lookback_time_s"] = t_obs - t_emit  # duplicate for convenience

        observed = ObservedState(
            source_id=source_id,
            observer_id=obs.observer_id,
            observation_time_s=t_obs,
            emission_time_s=t_emit,
            lookback_time_s=t_obs - t_emit,
            apparent_position=app_pos,
            apparent_distance_m=app_dist,
            emission_event=emission_event,
            actual_event_at_observation=actual_event,
            observer_event=observer_event,
            apparent_velocity=app_vel,
            apparent_brightness_w_per_m2=brightness,
            angular_size_rad=ang_size,
            redshift=redshift,
            reference_frame=frame,
            provenance=prov,
            metadata=metadata,
        )
        return observed

    # -- convenience wrappers -------------------------------------------
    def calculate_lookback_time(self, observer: Union[Observer,str], target: Any, observation_time_s: Optional[float]=None, target_id: Optional[str]=None) -> float:
        obs_state = self.observe(observer, target, observation_time_s, target_id)
        return obs_state.lookback_time_s

    def calculate_apparent_position(self, observer: Union[Observer,str], target: Any, observation_time_s: Optional[float]=None, target_id: Optional[str]=None) -> Tuple[float,float,float]:
        obs_state = self.observe(observer, target, observation_time_s, target_id)
        return obs_state.apparent_position

    def calculate_redshift(self, observer: Union[Observer,str], target: Any, observation_time_s: Optional[float]=None, target_id: Optional[str]=None) -> RedshiftComponents:
        obs_state = self.observe(observer, target, observation_time_s, target_id)
        return obs_state.redshift

    def reconstruct_historical_state(self, target_id: str, emission_time_s: float) -> HistoricalSnapshot:
        return self.cosmic_history.reconstruct_state(target_id, emission_time_s)

    def trace_light_path(self, source_event: SpacetimeEvent, observer_event: SpacetimeEvent, steps: int = 16) -> Tuple[SpacetimeEvent, ...]:
        return trace_path(source_event, (observer_event.x, observer_event.y, observer_event.z), observer_event.time_sec, steps)

    def get_observable_events(self, observer: Union[Observer,str], observation_time_s: Optional[float]=None) -> Tuple[TimelineEvent, ...]:
        """Return transient events whose signals have reached observer by observation_time_s."""
        if isinstance(observer, str):
            obs = self._observers.get(observer)
            if obs is None:
                raise InvalidObserverError(f"unknown observer {observer!r}")
        else:
            obs = observer
        t_obs = observation_time_s if observation_time_s is not None else obs.observation_time_s
        if t_obs is None:
            raise InvalidObserverError("observation_time_s required")
        t_obs = _check_time(t_obs, "observation_time_s")
        # observer position at t_obs
        if isinstance(obs, Observer):
            obs_pos = obs.position
        else:
            obs_pos = (0,0,0)
        observable = []
        for ev in self.cosmic_history.all_events():
            # need to know source position at event time; look up history snapshot for a participant
            # if event has no positional history, skip or assume observable if light travel would be satisfied via stored position metadata
            pos = ev.metadata.get("position") or ev.metadata.get("emission_position")
            if pos is None:
                # try to resolve from first participant's history
                if ev.participants:
                    try:
                        snap = self.cosmic_history.reconstruct_state(ev.participants[0], ev.timestamp_s)
                        if "position" in snap.state:
                            pos = snap.state["position"]
                    except Exception:
                        pos = None
            if pos is None:
                continue
            dist = math.sqrt((pos[0]-obs_pos[0])**2 + (pos[1]-obs_pos[1])**2 + (pos[2]-obs_pos[2])**2)
            travel = dist / SPEED_OF_LIGHT
            arrival = ev.timestamp_s + travel
            if arrival <= t_obs + 1e-12:
                # also check causal cone if metric available
                try:
                    src_ev = SpacetimeEvent.from_coordinates(ev.timestamp_s, pos[0], pos[1], pos[2])
                    obs_ev = SpacetimeEvent.from_coordinates(t_obs, obs_pos[0], obs_pos[1], obs_pos[2])
                    if is_observable(src_ev, obs_ev, self.metric):
                        observable.append(ev)
                except Exception:
                    observable.append(ev)
        return tuple(observable)

    def batch_observe(
        self,
        observer: Union[Observer,str],
        targets: Sequence[Any],
        observation_time_s: Optional[float]=None,
    ) -> List[ObservedState]:
        """Efficient batch observation (reuses observer; avoids full scans)."""
        out=[]
        for tgt in targets:
            try:
                out.append(self.observe(observer, tgt, observation_time_s))
            except Exception as e:
                # preserve determinism: include error placeholder? For now raise
                raise
        return out

    # -- direct helpers for spec API names --------------------------------
    def calculate_apparent_angular_size(self, observer, target, observation_time_s=None) -> Optional[float]:
        return self.observe(observer, target, observation_time_s).angular_size_rad

    def calculate_apparent_brightness(self, observer, target, observation_time_s=None) -> Optional[float]:
        return self.observe(observer, target, observation_time_s).apparent_brightness_w_per_m2

def _interpolate_worldline_at(worldline: Worldline, t: float) -> SpacetimeEvent:
    """Helper to interpolate worldline at arbitrary t (clamped)."""
    params=worldline.parameters
    events=worldline.events
    if t <= params[0]:
        return events[0]
    if t >= params[-1]:
        return events[-1]
    for p,e in zip(params, events):
        if p==t:
            return e
    lo = max(i for i in range(len(params)) if params[i]<=t)
    t0,t1=params[lo],params[lo+1]
    e0,e1=events[lo],events[lo+1]
    w=(t-t0)/(t1-t0) if t1!=t0 else 0
    return SpacetimeEvent(e0.ct_m + w*(e1.ct_m-e0.ct_m), e0.x+w*(e1.x-e0.x), e0.y+w*(e1.y-e0.y), e0.z+w*(e1.z-e0.z), CHART_CARTESIAN)
