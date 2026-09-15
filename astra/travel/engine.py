"""TravelEngine — top-level orchestration. Reconciled with real ASTRA.

Scaffold API preserved for compatibility; internals delegate to
authoritative ASTRA modules (relativity, spacetime, blackhole, temporal
causality, observation) when no mock provider is injected.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .config import TravelConfig
from .errors import (
    TravelAuthorityError,
    TravelCausalityError,
    TravelError,
    TravelNumericalError,
    TravelUnsupportedError,
    TravelValidationError,
)
from .integration import (
    DefaultAuthorityProvider,
    DefaultBlackHoleProvider,
    DefaultMeasurementProvider,
    DefaultObservationProvider,
    DefaultRelativityProvider,
    DefaultSpacecraftStateProvider,
    DefaultSpacetimeProvider,
    DefaultTemporalCausalityProvider,
)
from .state import TravelState, Transition
from .types import (
    ArrivalState,
    CausalStatus,
    Mechanism,
    Provenance,
    TravelEvent,
    TravelRequest,
    Vec3,
    Worldline,
    _to_vec3,
)
from .worldline import build_worldline

# For type checking against real Vector3
try:
    from astra.mathematics import Vector3  # noqa
except Exception:  # pragma: no cover
    Vector3 = None  # type: ignore


@dataclass
class TravelEngine:
    config: TravelConfig = field(default_factory=TravelConfig)

    authority: Optional[Any] = None
    relativity: Optional[Any] = None
    spacetime: Optional[Any] = None
    blackhole: Optional[Any] = None
    causality: Optional[Any] = None
    observation: Optional[Any] = None
    measurement: Optional[Any] = None
    spacecraft: Optional[Any] = None

    _travels: Dict[str, TravelEvent] = field(default_factory=dict, init=False)
    _states: Dict[str, TravelState] = field(default_factory=dict, init=False)
    _observation_records: Dict[str, Any] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.config.validate()
        # install defaults where not injected (keeps scaffold tests green when they inject mocks)
        if self.authority is None:
            self.authority = DefaultAuthorityProvider()
        if self.relativity is None:
            self.relativity = DefaultRelativityProvider()
        if self.spacetime is None:
            self.spacetime = DefaultSpacetimeProvider()
        if self.blackhole is None:
            self.blackhole = DefaultBlackHoleProvider()
        if self.causality is None:
            self.causality = DefaultTemporalCausalityProvider()
        if self.observation is None:
            self.observation = DefaultObservationProvider()
        if self.measurement is None:
            self.measurement = DefaultMeasurementProvider()
        if self.spacecraft is None:
            self.spacecraft = DefaultSpacecraftStateProvider()

    # -------------------------------------------------------------- API

    def get_state(self, travel_id: str) -> TravelState:
        return self._states.get(travel_id, TravelState.UNCONFIGURED)

    def execute(self, request: TravelRequest) -> TravelEvent:
        """Run a full travel pipeline.

        Strictly separates physical/spacetime/travel/observer/temporal/
        causal/measured layers as required.
        """
        self._require_authority("travel.execute")
        self._validate(request)

        travel_id = request.request_id
        self._set_state(travel_id, TravelState.READY)

        # Mechanism dispatch
        try:
            self._set_state(travel_id, TravelState.ACTIVE)
            event = self._execute_mechanism(request)
        except TravelUnsupportedError:
            # ensure state reflects unsupported
            try:
                self._set_state(travel_id, TravelState.PHYSICALLY_UNSUPPORTED)
            except TravelValidationError:
                pass
            raise
        except TravelCausalityError:
            try:
                self._set_state(travel_id, TravelState.CAUSALLY_INVALID)
            except TravelValidationError:
                pass
            raise
        except TravelError:
            try:
                self._set_state(travel_id, TravelState.FAILED)
            except TravelValidationError:
                pass
            raise
        except Exception as e:
            # map unexpected numerical issues to explicit failure
            if isinstance(e, (ValueError, ArithmeticError)) or "numerical" in str(type(e).__name__).lower():
                try:
                    self._set_state(travel_id, TravelState.FAILED)
                except TravelValidationError:
                    pass
                raise TravelNumericalError(str(e)) from e
            try:
                self._set_state(travel_id, TravelState.FAILED)
            except TravelValidationError:
                pass
            raise

        self._set_state(travel_id, TravelState.STABLE)
        self._travels[travel_id] = event
        # observation integration — record departure/arrival with finite light propagation
        try:
            self._record_observation(event, request)
        except Exception:
            # observation failures should not abort travel; record is best-effort
            pass
        # spacecraft integration — preserve/apply state if spacecraft traveler
        try:
            self._apply_spacecraft_arrival(event, request)
        except Exception:
            pass
        self._set_state(travel_id, TravelState.COMPLETED)
        return event

    def arrival_state(self, event: TravelEvent) -> ArrivalState:
        # Resolve velocity at arrival from worldline last segment or request velocity
        # Scaffold used 0, but we preserve departure velocity direction for realism
        vel = Vec3(0.0, 0.0, 0.0)
        try:
            if len(event.worldline.samples) >= 2:
                # estimate velocity from last segment delta / dt
                a = event.worldline.samples[-2]
                b = event.worldline.samples[-1]
                dt = b.coordinate_time_s - a.coordinate_time_s
                if dt != 0:
                    dx = b.position - a.position
                    vel = Vec3(dx.x / dt, dx.y / dt, dx.z / dt)
        except Exception:
            vel = Vec3(0.0, 0.0, 0.0)
        # clamp superluminal local estimates (numerical noise)
        from astra.relativity.core import SPEED_OF_LIGHT

        if vel.norm() >= SPEED_OF_LIGHT:
            # interior warp bubble may have coordinate velocity >c but local 0; keep as is for warp, else clamp
            if event.mechanism not in (Mechanism.WARP, Mechanism.WORMHOLE):
                # scale down slightly
                vel = vel * (0.999 * SPEED_OF_LIGHT / max(vel.norm(), 1.0))

        return ArrivalState(
            travel_id=event.travel_id,
            traveler_id=event.traveler_id,
            position=event.arrival_position,
            velocity=vel,
            orientation=None,
            proper_time_s=event.proper_elapsed_time_s,
            coordinate_time_s=event.arrival_coordinate_time_s,
            reference_frame=event.arrival_reference_frame,
            causal_status=event.causal_status,
            provenance=event.provenance,
            metadata=dict(event.metadata),
        )

    def diagnostics(self) -> Dict[str, Any]:
        return {
            "travels": len(self._travels),
            "model_version": self.config.model_version,
            "states": {k: v.value for k, v in self._states.items()},
        }

    def get_travel(self, travel_id: str) -> Optional[TravelEvent]:
        return self._travels.get(travel_id)

    # -------------------------------------------------------------- internals

    def _require_authority(self, operation: str) -> None:
        if self.authority is None:
            raise TravelAuthorityError(f"no AuthorityProvider configured; cannot perform {operation}")
        # authority may be scaffold _AllowAll/_DenyAll or real provider
        try:
            self.authority.require(operation)
        except TravelAuthorityError:
            raise
        except Exception as e:
            # map core AuthorityError
            from astra.core.exceptions import AuthorityError as CoreAuthErr

            if isinstance(e, CoreAuthErr):
                raise TravelAuthorityError(str(e), operation=operation) from e
            raise TravelAuthorityError(str(e), operation=operation) from e

    def _validate(self, request: TravelRequest) -> None:
        if not isinstance(request, TravelRequest):
            raise TravelValidationError("request must be TravelRequest")
        if request.request_id in self._travels:
            raise TravelValidationError(f"travel_id {request.request_id} already exists")
        # requested arrival must be >= departure
        if (
            request.requested_arrival_coordinate_time_s is not None
            and request.requested_arrival_coordinate_time_s < request.departure_coordinate_time_s - 1e-12
        ):
            raise TravelValidationError("requested arrival precedes departure")
        # positions finite already validated by Vec3, but check distance overflow
        dep = request.departure_position
        dst = request.destination_position
        delta = dst - dep
        # detect overflow in distance
        dist = delta.norm()
        if math.isnan(dist) or math.isinf(dist):
            raise TravelNumericalError("distance computation overflow")
        # mechanism-specific validation deferred to _execute_mechanism so that
        # state transitions to PHYSICALLY_UNSUPPORTED are correctly recorded
        # after READY/ACTIVE.  Only generic validation stays here.

    def _set_state(self, travel_id: str, new_state: TravelState) -> None:
        current = self._states.get(travel_id, TravelState.UNCONFIGURED)
        Transition.apply(current, new_state)
        self._states[travel_id] = new_state

    def _execute_mechanism(self, request: TravelRequest) -> TravelEvent:
        if request.mechanism == Mechanism.RELATIVISTIC:
            return self._execute_relativistic(request)
        if request.mechanism == Mechanism.WORMHOLE:
            return self._execute_wormhole(request)
        if request.mechanism == Mechanism.WARP:
            return self._execute_warp(request)
        if request.mechanism == Mechanism.WHITE_HOLE:
            return self._execute_white_hole(request)
        if request.mechanism == Mechanism.GRAVITATIONAL:
            return self._execute_gravitational(request)
        raise TravelUnsupportedError(f"unknown mechanism: {request.mechanism}")

    # -------------------------------------------------------- mechanisms

    def _causal_status_for(self, dep_pos: Vec3, dep_t: float, arr_pos: Vec3, arr_t: float) -> CausalStatus:
        # Use causality provider if available, else default to TIMELIKE for subluminal
        try:
            if self.causality is not None:
                result = self.causality.check_causal_order(
                    (dep_t, dep_pos.to_tuple()),
                    (arr_t, arr_pos.to_tuple()),
                )
                if isinstance(result, CausalStatus):
                    return result
                # provider may return string
                if isinstance(result, str):
                    try:
                        return CausalStatus(result)
                    except Exception:
                        pass
        except TravelCausalityError:
            raise
        except Exception:
            pass
        # fallback: classify via distance / c
        from astra.relativity.core import SPEED_OF_LIGHT

        dist = (arr_pos - dep_pos).norm()
        dt = arr_t - dep_t
        if dt < 0:
            return CausalStatus.CAUSALLY_INVALID
        # lightlike threshold
        light_dist = dt * SPEED_OF_LIGHT
        eps = 1e-9 * max(1.0, light_dist)
        if abs(dist - light_dist) <= eps:
            return CausalStatus.LIGHTLIKE
        if dist < light_dist:
            return CausalStatus.TIMELIKE
        return CausalStatus.SPACELIKE

    def _execute_relativistic(self, request: TravelRequest) -> TravelEvent:
        if self.relativity is None:
            raise TravelUnsupportedError("relativity provider not configured")

        dep_pos = request.departure_position
        arr_pos = request.destination_position
        delta = arr_pos - dep_pos
        distance = delta.norm()
        # speed from departure velocity
        vel = request.departure_velocity
        speed = vel.norm()
        if speed <= 0.0:
            raise TravelValidationError("relativistic travel requires non-zero velocity")
        # superluminal check: any local >c is forbidden for this mechanism
        from astra.relativity.core import SPEED_OF_LIGHT

        if speed >= SPEED_OF_LIGHT:
            raise TravelUnsupportedError(f"relativistic speed {speed} >= c ({SPEED_OF_LIGHT})")
        # allow requested arrival to override physics? We must respect requested but also enforce physics
        if request.requested_arrival_coordinate_time_s is not None:
            coordinate_dt = request.requested_arrival_coordinate_time_s - request.departure_coordinate_time_s
            if coordinate_dt < 0:
                raise TravelValidationError("requested arrival precedes departure")
            # check if required speed would be superluminal
            required_speed = distance / coordinate_dt if coordinate_dt != 0 else float("inf")
            if required_speed >= SPEED_OF_LIGHT:
                raise TravelCausalityError(
                    f"requested interval requires superluminal speed {required_speed} >= c without spacetime mechanism"
                )
            # proper time computed via lorentz with actual velocity (not required speed) — preserve physical consistency
            # If requested_dt is larger than physics dt, traveler would need to wait; we use requested_dt as coordinate_elapsed
            # but proper still from lorentz at given velocity for that coordinate interval
            try:
                gamma = self.relativity.lorentz_factor(vel)  # may be Vec3 or Vector3
            except Exception as e:
                # try with speed magnitude
                gamma = self.relativity.lorentz_factor(speed)
            proper_dt = coordinate_dt / gamma
            arrival_time = request.requested_arrival_coordinate_time_s
        else:
            coordinate_dt = distance / speed
            if math.isnan(coordinate_dt) or math.isinf(coordinate_dt):
                raise TravelNumericalError("coordinate duration overflow")
            # gamma via provider
            try:
                gamma = self.relativity.lorentz_factor(vel)
            except Exception:
                try:
                    gamma = self.relativity.lorentz_factor(speed)
                except Exception as e:
                    raise TravelNumericalError(str(e)) from e
            proper_dt = coordinate_dt / gamma
            arrival_time = request.departure_coordinate_time_s + coordinate_dt

        # numerical guards
        if math.isnan(proper_dt) or math.isinf(proper_dt):
            raise TravelNumericalError("proper time overflow")

        worldline = build_worldline(
            dep_pos,
            request.departure_coordinate_time_s,
            arr_pos,
            arrival_time,
            proper_dt,
            self.config,
            observer_frame=request.departure_reference_frame,
            provenance=Provenance.SIMULATED_DATA,
        )

        causal = self._causal_status_for(dep_pos, request.departure_coordinate_time_s, arr_pos, arrival_time)
        # relativistic matter must be timelike; spacelike is causally invalid
        if causal == CausalStatus.SPACELIKE:
            raise TravelCausalityError("relativistic travel produced spacelike separation (requires FTL)")
        if causal == CausalStatus.CAUSALLY_INVALID:
            raise TravelCausalityError("arrival precedes departure (causally invalid)")

        # energy / momentum diagnostics (classified as DERIVED / SIMULATED)
        energy_J = None
        momentum = None
        exhaust = "unknown"
        try:
            mass_kg = float(request.config.get("rest_mass_kg", 1.0))
            # only if mass provided and relativity provider supports energy
            if hasattr(self.relativity, "relativistic_energy"):
                energy_J = self.relativity.relativistic_energy(mass_kg, vel)
                exhaust = "calculated"
            elif hasattr(self.relativity, "relativistic_momentum"):
                momentum = self.relativity.relativistic_momentum(mass_kg, vel)
                exhaust = "calculated"
        except Exception:
            exhaust = "unknown"

        return TravelEvent(
            travel_id=request.request_id,
            traveler_id=request.traveler_id,
            mechanism=Mechanism.RELATIVISTIC,
            departure_position=dep_pos,
            departure_coordinate_time_s=request.departure_coordinate_time_s,
            departure_reference_frame=request.departure_reference_frame,
            arrival_position=arr_pos,
            arrival_coordinate_time_s=arrival_time,
            arrival_reference_frame=request.destination_reference_frame,
            proper_elapsed_time_s=proper_dt,
            coordinate_elapsed_time_s=arrival_time - request.departure_coordinate_time_s,
            observer_elapsed_time_s=arrival_time - request.departure_coordinate_time_s,
            causal_status=causal if causal != CausalStatus.UNKNOWN else CausalStatus.TIMELIKE,
            worldline=worldline,
            provenance=Provenance.SIMULATED_DATA,
            metadata={
                "gamma": float(gamma) if "gamma" in locals() else None,
                "distance_m": float(distance),
                "speed_m_s": float(speed),
                "energy_J": energy_J,
                "momentum": str(momentum) if momentum is not None else None,
                "exotic_matter_requirement": exhaust,
                "departure_event": {
                    "position": dep_pos.to_tuple(),
                    "time_s": request.departure_coordinate_time_s,
                    "frame": request.departure_reference_frame,
                },
                "arrival_event": {
                    "position": arr_pos.to_tuple(),
                    "time_s": arrival_time,
                    "frame": request.destination_reference_frame,
                },
                "observation_history": [],
            },
        )

    def _execute_gravitational(self, request: TravelRequest) -> TravelEvent:
        # Strong-field: delegate gravitational dilation to blackhole provider
        # If no mass config, fallback to relativistic with added note
        dep_pos = request.departure_position
        arr_pos = request.destination_position
        delta = arr_pos - dep_pos
        distance = delta.norm()
        vel = request.departure_velocity
        speed = vel.norm()
        if speed <= 0:
            raise TravelValidationError("gravitational travel requires non-zero velocity")

        from astra.relativity.core import SPEED_OF_LIGHT

        if speed >= SPEED_OF_LIGHT:
            raise TravelUnsupportedError("local speed >= c forbidden even in strong field")
        coordinate_dt = distance / speed if request.requested_arrival_coordinate_time_s is None else (
            request.requested_arrival_coordinate_time_s - request.departure_coordinate_time_s
        )
        if coordinate_dt < 0:
            raise TravelValidationError("arrival precedes departure")
        # velocity dilation
        try:
            gamma = self.relativity.lorentz_factor(vel)
        except Exception:
            gamma = self.relativity.lorentz_factor(speed)
        proper_velocity = coordinate_dt / gamma
        # gravitational factor if mass/radius supplied
        grav_factor = 1.0
        mass_kg = request.config.get("mass_kg") or request.config.get("black_hole_mass_kg")
        radius_m = request.config.get("radius_m") or request.config.get("orbit_radius_m", 1e9)
        if mass_kg is not None and self.blackhole is not None:
            try:
                # gravitational_time_dilation returns dt/dtau
                dilation = self.blackhole.gravitational_time_dilation(float(radius_m), float(mass_kg))
                # dtau = dt / dilation → grav_factor = 1/dilation
                grav_factor = 1.0 / dilation if dilation != 0 else 1.0
                # combined proper time: velocity then gravitational
                proper_dt = proper_velocity * grav_factor
                # also compute gravitational redshift for measurement
                redshift = None
                try:
                    r_obs = request.config.get("observer_radius_m", float(radius_m) * 2)
                    redshift = self.blackhole.gravitational_redshift(float(radius_m), float(r_obs), float(mass_kg))
                except Exception:
                    redshift = None
            except Exception:
                proper_dt = proper_velocity
                redshift = None
        else:
            proper_dt = proper_velocity
            redshift = None

        if math.isnan(proper_dt) or math.isinf(proper_dt):
            raise TravelNumericalError("gravitational proper time overflow")

        arrival_time = request.departure_coordinate_time_s + coordinate_dt
        worldline = build_worldline(
            dep_pos,
            request.departure_coordinate_time_s,
            arr_pos,
            arrival_time,
            proper_dt,
            self.config,
            observer_frame=request.departure_reference_frame,
            provenance=Provenance.SIMULATED_DATA,
        )

        causal = self._causal_status_for(dep_pos, request.departure_coordinate_time_s, arr_pos, arrival_time)
        if causal == CausalStatus.SPACELIKE:
            raise TravelCausalityError("gravitational travel produced spacelike separation")

        return TravelEvent(
            travel_id=request.request_id,
            traveler_id=request.traveler_id,
            mechanism=Mechanism.GRAVITATIONAL,
            departure_position=dep_pos,
            departure_coordinate_time_s=request.departure_coordinate_time_s,
            departure_reference_frame=request.departure_reference_frame,
            arrival_position=arr_pos,
            arrival_coordinate_time_s=arrival_time,
            arrival_reference_frame=request.destination_reference_frame,
            proper_elapsed_time_s=proper_dt,
            coordinate_elapsed_time_s=coordinate_dt,
            observer_elapsed_time_s=coordinate_dt,
            causal_status=causal if causal != CausalStatus.UNKNOWN else CausalStatus.TIMELIKE,
            worldline=worldline,
            provenance=Provenance.SIMULATED_DATA,
            metadata={
                "gamma": float(gamma),
                "gravitational_factor": float(grav_factor),
                "gravitational_redshift": redshift,
                "distance_m": float(distance),
                "speed_m_s": float(speed),
                "exotic_matter_requirement": "unknown",
                "departure_event": {
                    "position": dep_pos.to_tuple(),
                    "time_s": request.departure_coordinate_time_s,
                    "frame": request.departure_reference_frame,
                },
                "arrival_event": {"position": arr_pos.to_tuple(), "time_s": arrival_time, "frame": request.destination_reference_frame},
            },
        )

    def _execute_wormhole(self, request: TravelRequest) -> TravelEvent:
        from .wormhole import Wormhole, traverse

        wh_cfg = request.config.get("wormhole")
        if wh_cfg is None:
            raise TravelUnsupportedError("wormhole config missing from request")
        # allow Wormhole instance or dict containing Wormhole
        if isinstance(wh_cfg, dict) and "wormhole_id" in wh_cfg and not isinstance(wh_cfg, Wormhole):
            # attempt to build Wormhole from dict? For now raise to force proper type
            raise TravelUnsupportedError("wormhole config dict must be Wormhole instance")
        wh = wh_cfg  # expected Wormhole
        if not isinstance(wh, Wormhole):
            raise TravelUnsupportedError("wormhole config must be Wormhole instance")

        descriptor = traverse(wh, request.traveler_id, request.departure_coordinate_time_s)

        arrival_time = float(descriptor["arrival_coordinate_time_s"])
        proper_dt = float(descriptor["proper_duration_s"])

        # respect requested arrival if provided and not violating causality? Use descriptor arrival if not forced
        if request.requested_arrival_coordinate_time_s is not None:
            # wormhole traversal duration is intrinsic; requested may be later → wait at mouth B
            if request.requested_arrival_coordinate_time_s < arrival_time - 1e-9:
                raise TravelCausalityError("requested arrival precedes wormhole traversal completion")
            arrival_time = float(request.requested_arrival_coordinate_time_s)
            # proper stays as traversal proper + waiting (waiting is coordinate = proper)
            proper_dt = proper_dt + (arrival_time - float(descriptor["arrival_coordinate_time_s"]))

        # Build worldline via mouth positions (through topology — not linear in ambient space, but scaffold linear)
        # For physics detail we could use proper_radial_distance, but keep deterministic linear for now
        worldline = build_worldline(
            request.departure_position,
            request.departure_coordinate_time_s,
            request.destination_position,
            arrival_time,
            proper_dt,
            self.config,
            observer_frame=request.departure_reference_frame,
            provenance=Provenance.HYPOTHETICAL,
        )

        causal = CausalStatus.UNKNOWN
        if self.causality is not None:
            try:
                result = self.causality.check_causal_order(
                    (request.departure_coordinate_time_s, request.departure_position.to_tuple()),
                    (arrival_time, request.destination_position.to_tuple()),
                )
                if isinstance(result, CausalStatus):
                    causal = result
                elif isinstance(result, str):
                    try:
                        causal = CausalStatus(result)
                    except Exception:
                        pass
            except Exception:
                pass

        # wormhole chronology diagnostic — report CTC possibility
        ctc_possible = False
        try:
            from astra.temporal.exotic import wormhole_chronology_diagnostic
            # need a metric — try to retrieve from descriptor or build
            # we have wh.metric_parameters, build a temporary MorrisThorne for diagnostic
            from astra.theoretical.wormhole import MorrisThorneMetric

            # use default shape if needed
            r0 = float(wh.metric_parameters.get("throat_radius_m", 1e3))

            def _shape(r):
                return (r0 * r0) / r if r != 0 else r0

            metric = MorrisThorneMetric(r0, _shape)
            diag = wormhole_chronology_diagnostic(metric, [r0 * 2, r0 * 5])
            ctc_possible = diag.chronology_violation_possible
        except Exception:
            ctc_possible = False

        if ctc_possible:
            causal = CausalStatus.CTC
        if causal == CausalStatus.CAUSALLY_INVALID:
            raise TravelCausalityError("wormhole traversal violates causality")

        return TravelEvent(
            travel_id=request.request_id,
            traveler_id=request.traveler_id,
            mechanism=Mechanism.WORMHOLE,
            departure_position=request.departure_position,
            departure_coordinate_time_s=request.departure_coordinate_time_s,
            departure_reference_frame=request.departure_reference_frame,
            arrival_position=request.destination_position,
            arrival_coordinate_time_s=arrival_time,
            arrival_reference_frame=request.destination_reference_frame,
            proper_elapsed_time_s=proper_dt,
            coordinate_elapsed_time_s=arrival_time - request.departure_coordinate_time_s,
            observer_elapsed_time_s=arrival_time - request.departure_coordinate_time_s,
            causal_status=causal,
            worldline=worldline,
            provenance=Provenance.HYPOTHETICAL,
            metadata={
                "wormhole_id": wh.wormhole_id,
                "stability": wh.stability,
                "ctc_possible": ctc_possible,
                "exotic_matter_requirement": "hypothetical",
                "metric_parameters": dict(wh.metric_parameters),
                "departure_event": {
                    "position": request.departure_position.to_tuple(),
                    "time_s": request.departure_coordinate_time_s,
                },
                "arrival_event": {"position": request.destination_position.to_tuple(), "time_s": arrival_time},
            },
        )

    def _execute_warp(self, request: TravelRequest) -> TravelEvent:
        from .warp import WarpConfig, warp_travel_descriptor

        warp_cfg = request.config.get("warp")
        if warp_cfg is None or not isinstance(warp_cfg, WarpConfig):
            # also allow WarpBubble directly for flexibility
            if isinstance(warp_cfg, dict) and "bubble" in warp_cfg:
                raise TravelUnsupportedError("warp config dict must be WarpConfig instance")
            raise TravelUnsupportedError("warp config missing from request (expected WarpConfig)")

        dep_pos = request.departure_position
        arr_pos = request.destination_position
        distance = (arr_pos - dep_pos).norm()

        # if requested arrival provided, could imply different bubble velocity is needed — we honor descriptor but check superluminal rule
        descriptor = warp_travel_descriptor(
            warp_cfg, request.traveler_id, request.departure_coordinate_time_s, distance
        )

        arrival_time = float(descriptor["arrival_coordinate_time_s"])
        proper_dt = float(descriptor["proper_duration_s"])

        if request.requested_arrival_coordinate_time_s is not None:
            # requested may be later → loiter, earlier → need faster bubble (unsupported)
            if request.requested_arrival_coordinate_time_s < arrival_time - 1e-9:
                raise TravelUnsupportedError("requested arrival requires faster-than-configured warp bubble")
            # extend proper/coordinate by waiting
            wait = float(request.requested_arrival_coordinate_time_s) - arrival_time
            arrival_time = float(request.requested_arrival_coordinate_time_s)
            proper_dt = proper_dt + wait

        worldline = build_worldline(
            dep_pos,
            request.departure_coordinate_time_s,
            arr_pos,
            arrival_time,
            proper_dt,
            self.config,
            observer_frame=request.departure_reference_frame,
            provenance=Provenance.THEORETICAL,
        )

        # causality — warp is coordinate FTL but locally causal; we report UNKNOWN or TIMELIKE locally
        causal = CausalStatus.UNKNOWN
        # For measurement integration: attempt warp cone analysis
        cone_tilted = None
        try:
            from astra.temporal.exotic import warp_cone_analysis

            metric = descriptor.get("metric")
            if metric is not None:
                # analyze at bubble center at departure
                from astra.relativity.core import SPEED_OF_LIGHT

                coords = (request.departure_coordinate_time_s * SPEED_OF_LIGHT, dep_pos.x, dep_pos.y, dep_pos.z)
                analysis = warp_cone_analysis(metric, coords)
                cone_tilted = analysis.tilted_cone
        except Exception:
            cone_tilted = None

        return TravelEvent(
            travel_id=request.request_id,
            traveler_id=request.traveler_id,
            mechanism=Mechanism.WARP,
            departure_position=dep_pos,
            departure_coordinate_time_s=request.departure_coordinate_time_s,
            departure_reference_frame=request.departure_reference_frame,
            arrival_position=arr_pos,
            arrival_coordinate_time_s=arrival_time,
            arrival_reference_frame=request.destination_reference_frame,
            proper_elapsed_time_s=proper_dt,
            coordinate_elapsed_time_s=arrival_time - request.departure_coordinate_time_s,
            observer_elapsed_time_s=arrival_time - request.departure_coordinate_time_s,
            causal_status=causal,
            worldline=worldline,
            provenance=Provenance.THEORETICAL,
            metadata={
                "bubble_id": warp_cfg.bubble.bubble_id,
                "bubble_velocity_m_s": warp_cfg.bubble.bubble_velocity_m_s,
                "exotic_matter_requirement": warp_cfg.exotic_matter_requirement,
                "cone_tilted": cone_tilted,
                "distance_m": float(distance),
                "departure_event": {"position": dep_pos.to_tuple(), "time_s": request.departure_coordinate_time_s},
                "arrival_event": {"position": arr_pos.to_tuple(), "time_s": arrival_time},
            },
        )

    def _execute_white_hole(self, request: TravelRequest) -> TravelEvent:
        from .white_hole import WhiteHoleConfig

        cfg = request.config.get("white_hole") or request.config.get("whitehole") or request.config.get("whiteHole")
        if cfg is None:
            raise TravelUnsupportedError("white-hole config missing from request (expected WhiteHoleConfig)")
        if not isinstance(cfg, WhiteHoleConfig):
            raise TravelUnsupportedError("white-hole config must be WhiteHoleConfig")

        # White hole is THEORETICAL/HYPOTHETICAL, emissive only — travel is outward
        dep_pos = request.departure_position
        arr_pos = request.destination_position
        # verify outward vs causal direction
        delta = arr_pos - dep_pos
        # check emissive policy at departure coords
        from astra.relativity.core import SPEED_OF_LIGHT

        coords = (request.departure_coordinate_time_s * SPEED_OF_LIGHT, dep_pos.x, dep_pos.y, dep_pos.z)
        # need four_velocity — estimate from departure_velocity, future-directed u^0>0, u^r outward
        vel = request.departure_velocity
        speed = vel.norm()
        if speed >= SPEED_OF_LIGHT:
            raise TravelUnsupportedError("local speed >=c forbidden even for white-hole interface")
        # construct a plausible four_velocity in spherical chart? Use cartesian approximation (ct, x, y, z)
        # For policy check we need spherical coords: convert departure position to spherical
        try:
            from astra.spacetime.events import cartesian_to_spherical

            r, theta, phi = cartesian_to_spherical(dep_pos.x, dep_pos.y, dep_pos.z)
            # spherical coords (ct, r, theta, phi)
            sph_coords = (request.departure_coordinate_time_s * SPEED_OF_LIGHT, r, theta, phi)
            # radial unit vector
            if r > 0:
                radial = Vec3(dep_pos.x / r, dep_pos.y / r, dep_pos.z / r)
                vr = vel.dot(radial)
            else:
                vr = 0.0
            # future-directed
            gamma = 1.0
            try:
                gamma = self.relativity.lorentz_factor(vel) if self.relativity else 1.0
            except Exception:
                gamma = 1.0
            four_vel_sph = (gamma * SPEED_OF_LIGHT, gamma * vr, 0.0, 0.0)
            # delegate to whitehole metric policy via temporal check
            from .white_hole import check_emissive

            check = check_emissive(cfg, sph_coords, four_vel_sph)
            if not check["allowed"]:
                raise TravelCausalityError(f"white-hole emissive policy rejected: {check['reason']}")
        except TravelCausalityError:
            raise
        except Exception as e:
            # if conversion fails at origin spherical, use cartesian emissive check fallback (outward)
            if delta.norm() < 1e-9:
                raise TravelValidationError("white-hole travel requires spatial displacement outward")
            # check velocity is outward-ish
            if r > 0 and vel.dot(radial) < 0:
                raise TravelCausalityError("white-hole travel ingoing velocity rejected (emissive only)")

        # coordinate duration similar to relativistic but classified hypothetical
        distance = delta.norm()
        speed = vel.norm() if vel.norm() > 0 else 1e3  # default small speed if zero? but we already require non-zero? For white hole we may allow emergent flow
        if speed == 0:
            raise TravelValidationError("white-hole travel requires non-zero departure velocity (emergent flow)")
        coordinate_dt = distance / speed if request.requested_arrival_coordinate_time_s is None else (
            request.requested_arrival_coordinate_time_s - request.departure_coordinate_time_s
        )
        if coordinate_dt < 0:
            raise TravelValidationError("arrival precedes departure")
        try:
            gamma = self.relativity.lorentz_factor(vel) if self.relativity else 1.0
        except Exception:
            gamma = 1.0
        proper_dt = coordinate_dt / gamma if gamma != 0 else coordinate_dt

        arrival_time = request.departure_coordinate_time_s + coordinate_dt
        worldline = build_worldline(
            dep_pos,
            request.departure_coordinate_time_s,
            arr_pos,
            arrival_time,
            proper_dt,
            self.config,
            observer_frame=request.departure_reference_frame,
            provenance=Provenance.HYPOTHETICAL,
        )

        return TravelEvent(
            travel_id=request.request_id,
            traveler_id=request.traveler_id,
            mechanism=Mechanism.WHITE_HOLE,
            departure_position=dep_pos,
            departure_coordinate_time_s=request.departure_coordinate_time_s,
            departure_reference_frame=request.departure_reference_frame,
            arrival_position=arr_pos,
            arrival_coordinate_time_s=arrival_time,
            arrival_reference_frame=request.destination_reference_frame,
            proper_elapsed_time_s=proper_dt,
            coordinate_elapsed_time_s=coordinate_dt,
            observer_elapsed_time_s=coordinate_dt,
            causal_status=CausalStatus.TIMELIKE,
            worldline=worldline,
            provenance=Provenance.HYPOTHETICAL,
            metadata={
                "white_hole_id": cfg.white_hole_id,
                "causal_direction": cfg.causal_direction,
                "matter_flow_assumption": cfg.matter_flow_assumption,
                "exotic_matter_requirement": "hypothetical",
                "departure_event": {"position": dep_pos.to_tuple(), "time_s": request.departure_coordinate_time_s},
                "arrival_event": {"position": arr_pos.to_tuple(), "time_s": arrival_time},
            },
        )

    # ------------------------------------------------- observation & spacecraft

    def _record_observation(self, event: TravelEvent, request: TravelRequest) -> None:
        # Preserve finite light propagation: signal delay = distance / c to a generic observer at origin
        from astra.relativity.core import SPEED_OF_LIGHT

        # assume observer at (0,0,0) for delay estimate unless config provides observer_position
        obs_pos = request.config.get("observer_position") or (0.0, 0.0, 0.0)
        if isinstance(obs_pos, Vec3):
            obs_tuple = obs_pos.to_tuple()
        elif isinstance(obs_pos, (list, tuple)):
            obs_tuple = tuple(float(x) for x in obs_pos)
        else:
            obs_tuple = (0.0, 0.0, 0.0)
        dep = event.departure_position.to_tuple()
        arr = event.arrival_position.to_tuple()

        def delay(pos):
            d = math.sqrt((pos[0] - obs_tuple[0]) ** 2 + (pos[1] - obs_tuple[1]) ** 2 + (pos[2] - obs_tuple[2]) ** 2)
            return d / SPEED_OF_LIGHT

        dep_delay = delay(dep)
        arr_delay = delay(arr)
        # record via provider if it has method
        try:
            if hasattr(self.observation, "record_departure"):
                did = self.observation.record_departure(
                    {
                        "travel_id": event.travel_id,
                        "position": dep,
                        "time_s": event.departure_coordinate_time_s,
                        "delay_s": dep_delay,
                    }
                )
                self._observation_records[event.travel_id + ":dep"] = did
            if hasattr(self.observation, "record_arrival"):
                aid = self.observation.record_arrival(
                    {
                        "travel_id": event.travel_id,
                        "position": arr,
                        "time_s": event.arrival_coordinate_time_s,
                        "delay_s": arr_delay,
                    }
                )
                self._observation_records[event.travel_id + ":arr"] = aid
        except Exception:
            pass
        # also store in event metadata for inspection (not mutating frozen event — we already set metadata at creation;
        # store extra in engine sidecar)
        self._observation_records[event.travel_id] = {
            "departure_delay_s": dep_delay,
            "arrival_delay_s": arr_delay,
            "observed_departure_at": event.departure_coordinate_time_s + dep_delay,
            "observed_arrival_at": event.arrival_coordinate_time_s + arr_delay,
        }

    def _apply_spacecraft_arrival(self, event: TravelEvent, request: TravelRequest) -> None:
        # If traveler_id matches a spacecraft, update its MotionState position/velocity
        # Preserve mass, momentum, orientation where applicable
        try:
            state = None
            if hasattr(self.spacecraft, "get_state"):
                state = self.spacecraft.get_state(request.traveler_id)
            if state is None:
                return
            # expect SpacecraftState with motion attribute
            from astra.motion.state import MotionState

            arrival = self.arrival_state(event)
            # apply position/velocity to MotionState copy
            if hasattr(state, "motion") and isinstance(state.motion, MotionState):
                new_motion = state.motion.copy()
                # update position, velocity, time
                try:
                    from astra.mathematics import Vector3 as V3

                    new_motion.position = V3(*arrival.position.to_tuple())
                    new_motion.velocity = V3(*arrival.velocity.to_tuple())
                    new_motion.time = arrival.coordinate_time_s
                    # orientation preserved unless travel explicitly sets it
                    new_state = type(state)(motion=new_motion, mass=state.mass, engine_specs=list(state.engine_specs))
                    if hasattr(self.spacecraft, "apply_state"):
                        self.spacecraft.apply_state(request.traveler_id, new_state)
                except Exception:
                    pass
        except Exception:
            pass
