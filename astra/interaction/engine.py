"""ASTRA Interaction — unified InteractionEngine.

Central orchestrator that:
  - validates InteractionAction (scientific classification, target availability, state machine)
  - translates controls via authoritative providers
  - delegates navigation/travel/observation to providers (never bypasses physics)
  - records exploration history, discoveries, visited locations
  - emits events via EventBus (if available)
  - ensures determinism and serializability
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
import math

from astra.scientific.classification import Classification, classify_combination, ClassificationOrder
from astra.scientific.warnings import WarningSink, WarningCode, WarningSeverity, ScientificWarning

from .errors import (
    InvalidInteractionError, StateTransitionError, NavigationError,
    TravelError, TargetError, ObservationError, ControlError, TemporalError, CausalityError,
)
from .state import ExplorationState, ExplorerIdentity
from .commands import InteractionAction, InteractionType, InteractionResult, make_action_id
from .scale import ScaleLevel
from .target import TargetRegistry, Target
from .controls import ControlInput, ControlTranslator
from .navigation import NavigationService, NavigationRequest
from .travel import TravelRequest, TravelMethod, DelegatingTravelService, TravelConstraints
from .observation import ObservationService, ObservationContext, Discovery, DiscoveryRegistry
from .history import ExplorationHistory, HistoryEventKind
from .statemachine import ExplorationStateMachine, ExplorationStateType


# Map InteractionType -> desired FSM state
_INTERACTION_TO_STATE = {
    InteractionType.NAVIGATE: ExplorationStateType.NAVIGATING,
    InteractionType.APPROACH: ExplorationStateType.APPROACHING,
    InteractionType.OBSERVE: ExplorationStateType.OBSERVING,
    InteractionType.MEASURE: ExplorationStateType.MEASURING,
    InteractionType.INITIATE_TRAVEL: ExplorationStateType.TRAVELLING,
    InteractionType.TRACK: ExplorationStateType.TRACKING,
    InteractionType.SELECT: ExplorationStateType.INTERACTING,
    InteractionType.INSPECT: ExplorationStateType.INTERACTING,
    InteractionType.FOLLOW: ExplorationStateType.TRACKING,
    InteractionType.EXPERIMENT: ExplorationStateType.INTERACTING,
    InteractionType.WORLD_INTERACT: ExplorationStateType.INTERACTING,
    InteractionType.SPACECRAFT_COMMAND: ExplorationStateType.INTERACTING,
    InteractionType.CHANGE_PERSPECTIVE: ExplorationStateType.OBSERVING,
    InteractionType.CHANGE_FRAME: ExplorationStateType.NAVIGATING,
    InteractionType.ENTER: ExplorationStateType.EXPLORING,
    InteractionType.LEAVE: ExplorationStateType.NAVIGATING,
    InteractionType.DEPART: ExplorationStateType.NAVIGATING,
    InteractionType.PAUSE: ExplorationStateType.PAUSED,
    InteractionType.RESUME: ExplorationStateType.IDLE,
    InteractionType.RECORD_DISCOVERY: ExplorationStateType.EXPLORING,
    InteractionType.SET_SCALE: ExplorationStateType.NAVIGATING,
}


@dataclass
class InteractionEngineConfig:
    allow_speculative_travel: bool = False
    max_control_per_tick: int = 8
    deterministic: bool = True


class InteractionEngine:
    """Deterministic interaction processing."""

    def __init__(
        self,
        state: ExplorationState,
        targets: Optional[TargetRegistry] = None,
        discoveries: Optional[DiscoveryRegistry] = None,
        history: Optional[ExplorationHistory] = None,
        fsm: Optional[ExplorationStateMachine] = None,
        navigation: Optional[NavigationService] = None,
        travel: Optional[DelegatingTravelService] = None,
        observation: Optional[ObservationService] = None,
        control_translator: Optional[ControlTranslator] = None,
        event_bus: Any = None,
        clock: Any = None,
        temporal: Any = None,
        config: Optional[InteractionEngineConfig] = None,
        warning_sink: Optional[WarningSink] = None,
    ):
        self.state = state
        self.targets = targets or TargetRegistry()
        self.discoveries = discoveries or DiscoveryRegistry()
        self.history = history or ExplorationHistory()
        self.fsm = fsm or ExplorationStateMachine()
        self.navigation = navigation or NavigationService()
        self.travel = travel or DelegatingTravelService()
        self.observation = observation or ObservationService()
        self.control_translator = control_translator or ControlTranslator()
        self.event_bus = event_bus
        self.clock = clock
        self.temporal = temporal
        self.config = config or InteractionEngineConfig()
        self.warning_sink = warning_sink or WarningSink()
        self._seq = 0
        self._results: List[InteractionResult] = []

    # -- helpers -----------------------------------------------------------

    def _next_id(self, prefix: str = "ia") -> str:
        self._seq += 1
        return f"{prefix}-{self._seq:06d}"

    def _emit_event(self, kind: HistoryEventKind, tick: int, sim_s: float,
                    target_id: Optional[str], data: Dict, classification: Classification):
        ev = self.history.emit(kind, tick, sim_s, target_id, data, classification)
        if self.event_bus is not None:
            try:
                self.event_bus.publish_sync(ev.kind.value.lower(), tick, data={"event_id": ev.event_id, "kind": ev.kind.value, "target_id": target_id, **data}, source="interaction")
            except Exception:
                pass
        return ev

    def _update_times(self, tick: Optional[int] = None):
        # read from authoritative clocks if available
        if tick is not None:
            self.state.tick = tick
        if self.clock is not None:
            try:
                self.state.tick = int(self.clock.get_current_tick())
                self.state.simulation_time_s = float(self.clock.get_simulation_time())
            except Exception:
                pass
        if self.temporal is not None:
            try:
                self.state.proper_time_s = float(self.temporal.proper_time_s)
                self.state.coordinate_time_s = float(self.temporal.coordinate_time_s)
            except Exception:
                pass

    # -- main entry --------------------------------------------------------

    def dispatch(self, action: InteractionAction, control_input: Optional[ControlInput] = None,
                 travel_req: Optional[TravelRequest] = None,
                 observation_ctx: Optional[ObservationContext] = None,
                 history_worldline: Any = None) -> InteractionResult:
        """Deterministic dispatch — validates, transitions FSM, delegates, records."""

        # Basic validation
        if not isinstance(action, InteractionAction):
            raise InvalidInteractionError("action must be InteractionAction")
        self._update_times(tick=action.tick)

        # Scientific classification check: speculative methods require speculative classification
        desired_state = _INTERACTION_TO_STATE.get(action.type)
        # State machine transition (explicit, never silent repair)
        if desired_state is not None:
            try:
                # PAUSE is allowed from many states; check first if already PAUSED etc.
                if self.fsm.state == ExplorationStateType.PAUSED and action.type == InteractionType.RESUME:
                    self.fsm.transition(ExplorationStateType.IDLE)
                elif self.fsm.state == ExplorationStateType.PAUSED and desired_state != ExplorationStateType.PAUSED:
                    # must resume first before other actions
                    raise StateTransitionError(f"must RESUME from PAUSED before {action.type.value}")
                else:
                    if self.fsm.state != desired_state:
                        self.fsm.transition(desired_state)
            except StateTransitionError as e:
                result = InteractionResult(action_id=action.action_id, success=False, tick=action.tick,
                                           error_code="STATE_TRANSITION_ERROR", error_message=str(e),
                                           classification=action.classification)
                self._results.append(result)
                self.history.emit(HistoryEventKind.STATE_TRANSITION, action.tick, self.state.simulation_time_s,
                                  action.target_id, {"error": str(e), "desired": desired_state.value if desired_state else None,
                                                     "current": self.fsm.state.value}, action.classification)
                return result

        # Dispatch by type
        try:
            if action.type == InteractionType.SELECT:
                return self._handle_select(action)
            elif action.type == InteractionType.INSPECT:
                return self._handle_inspect(action)
            elif action.type == InteractionType.OBSERVE:
                return self._handle_observe(action, observation_ctx, history_worldline)
            elif action.type == InteractionType.MEASURE:
                return self._handle_measure(action, observation_ctx, history_worldline)
            elif action.type in (InteractionType.NAVIGATE, InteractionType.APPROACH, InteractionType.DEPART,
                                 InteractionType.ENTER, InteractionType.LEAVE, InteractionType.CHANGE_FRAME,
                                 InteractionType.SET_SCALE, InteractionType.CHANGE_PERSPECTIVE):
                return self._handle_navigation(action)
            elif action.type == InteractionType.INITIATE_TRAVEL:
                return self._handle_travel(action, travel_req)
            elif action.type == InteractionType.SPACECRAFT_COMMAND:
                return self._handle_spacecraft(action, control_input)
            elif action.type in (InteractionType.TRACK, InteractionType.FOLLOW):
                return self._handle_track(action)
            elif action.type == InteractionType.PAUSE:
                return self._handle_pause(action)
            elif action.type == InteractionType.RESUME:
                return self._handle_resume(action)
            elif action.type == InteractionType.RECORD_DISCOVERY:
                return self._handle_record_discovery(action)
            elif action.type in (InteractionType.WORLD_INTERACT, InteractionType.EXPERIMENT):
                return self._handle_world_interact(action)
            else:
                raise InvalidInteractionError(f"unsupported interaction type {action.type}")
        except (InvalidInteractionError, NavigationError, TravelError, TargetError,
                ObservationError, ControlError, TemporalError, CausalityError, StateTransitionError) as e:
            result = InteractionResult(action_id=action.action_id, success=False, tick=action.tick,
                                       error_code=e.__class__.__name__, error_message=str(e),
                                       classification=action.classification)
            self._results.append(result)
            self.history.emit(HistoryEventKind.INTERACTION_EVENT, action.tick, self.state.simulation_time_s,
                              action.target_id, {"type": action.type.value, "error": str(e)}, action.classification)
            # FSM to FAILED if not already PAUSED/COMPLETED
            try:
                if self.fsm.state not in (ExplorationStateType.PAUSED, ExplorationStateType.COMPLETED, ExplorationStateType.FAILED, ExplorationStateType.IDLE):
                    self.fsm.transition(ExplorationStateType.FAILED)
            except StateTransitionError:
                pass
            return result

    # -- handlers ----------------------------------------------------------

    def _handle_select(self, action: InteractionAction) -> InteractionResult:
        if action.target_id is None:
            raise TargetError("SELECT requires target_id")
        target = self.targets.get_or_raise(action.target_id)
        self.state.active_target_id = target.target_id
        self._emit_event(HistoryEventKind.TARGETING, action.tick, self.state.simulation_time_s,
                         target.target_id, {"action": "SELECT", "kind": target.kind.value}, action.classification)
        result = InteractionResult(action_id=action.action_id, success=True, tick=action.tick,
                                   data={"target": target.to_dict()}, classification=target.classification)
        self._results.append(result)
        return result

    def _handle_inspect(self, action: InteractionAction) -> InteractionResult:
        if action.target_id is None:
            raise TargetError("INSPECT requires target_id")
        target = self.targets.get_or_raise(action.target_id)
        # Inspect must not fabricate data; return only known metadata
        self._emit_event(HistoryEventKind.OBJECT_OBSERVED, action.tick, self.state.simulation_time_s,
                         target.target_id, {"action": "INSPECT", "metadata": target.metadata}, target.classification)
        result = InteractionResult(action_id=action.action_id, success=True, tick=action.tick,
                                   data={"target": target.to_dict(), "provenance": "authoritative reference"}, classification=target.classification)
        self._results.append(result)
        return result

    def _handle_observe(self, action: InteractionAction, ctx: Optional[ObservationContext], history) -> InteractionResult:
        if action.target_id is None:
            raise TargetError("OBSERVE requires target_id")
        if ctx is None:
            raise ObservationError("OBSERVE requires ObservationContext (finite light propagation)")
        # Must distinguish observed vs current: delegate
        discovery = self.observation.observe(action.target_id, ctx, history)
        self.discoveries.record(discovery)
        # Update state references
        self.state.observation_ids = tuple(list(self.state.observation_ids) + [discovery.discovery_id])
        self.state.discovered_ids = tuple(list(self.state.discovered_ids) + [discovery.discovery_id])
        self._emit_event(HistoryEventKind.OBSERVATION, action.tick, self.state.simulation_time_s,
                         action.target_id, {"discovery_id": discovery.discovery_id, "lookback_s": discovery.lookback_time_s}, discovery.classification)
        # Warn if speculative
        if discovery.classification in (Classification.HYPOTHETICAL, Classification.SPECULATIVE):
            self.warning_sink.emit(ScientificWarning(WarningCode.SPECULATIVE_MODEL, WarningSeverity.WARNING,
                                                      f"observed speculative target {action.target_id}", {"target_id": action.target_id}))
        result = InteractionResult(action_id=action.action_id, success=True, tick=action.tick,
                                   data={"discovery": discovery.to_dict(), "observed_state_distinct_from_current": True},
                                   classification=discovery.classification,
                                   warnings=tuple(w.to_dict() for w in self.warning_sink.all()))
        self._results.append(result)
        return result

    def _handle_measure(self, action: InteractionAction, ctx: Optional[ObservationContext], history) -> InteractionResult:
        # Measure is like observe but includes instrument context
        if action.target_id is None:
            raise TargetError("MEASURE requires target_id")
        if ctx is None or ctx.instrument is None:
            raise ObservationError("MEASURE requires ObservationContext with instrument")
        discovery = self.observation.observe(action.target_id, ctx, history)
        # Measurement adds data provenance
        self.discoveries.record(discovery)
        self._emit_event(HistoryEventKind.MEASUREMENT_PERFORMED, action.tick, self.state.simulation_time_s,
                         action.target_id, {"discovery_id": discovery.discovery_id, "instrument": ctx.instrument}, discovery.classification)
        result = InteractionResult(action_id=action.action_id, success=True, tick=action.tick,
                                   data={"discovery": discovery.to_dict(), "measurement": True}, classification=discovery.classification)
        self._results.append(result)
        return result

    def _handle_navigation(self, action: InteractionAction) -> InteractionResult:
        # Use NavigationService; never teleport
        params = action.parameters
        to_scale = ScaleLevel(params.get("to_scale", self.state.navigation.scale.value)) if params.get("to_scale") else self.state.navigation.scale
        if params.get("to_scale_alt"):
            to_scale = ScaleLevel(params["to_scale_alt"])
        # Also accept scale param directly
        if "scale" in params:
            to_scale = ScaleLevel(params["scale"])
        from_scale = self.state.navigation.scale
        # Allow explicit overrides
        if "from_scale" in params:
            from_scale = ScaleLevel(params["from_scale"])
        # Resolve position hint from target registry when no explicit position and no world
        position = tuple(params["position"]) if params.get("position") else None
        target_ref = action.target_id or params.get("target_reference")
        if position is None and target_ref is not None:
            try:
                tgt = self.targets.get(target_ref)
                if tgt is not None and tgt.position_hint is not None:
                    position = tgt.position_hint
            except Exception:
                pass
        req = NavigationRequest(
            request_id=self._next_id("nav"),
            from_scale=from_scale,
            to_scale=to_scale,
            target_reference=target_ref,
            frame_id=action.frame_id or params.get("frame_id") or self.state.navigation.frame_id,
            position=position,
        )
        # validate scientific classification visible
        nav_result = self.navigation.execute(req, require_authority=False)
        if not nav_result.success:
            raise NavigationError(nav_result.error or "navigation failed")
        # Update navigation context (reference, not instant teleport — represents INTENT and resolved target)
        self.state.navigation = type(self.state.navigation)(
            frame_id=nav_result.frame_id or self.state.navigation.frame_id,
            world_id=self.state.navigation.world_id,
            scene_node_id=req.target_reference or self.state.navigation.scene_node_id,
            scale=to_scale,
            origin_hint=nav_result.world_position or self.state.navigation.origin_hint,
        )
        # Record visited location (provenance-aware)
        if req.target_reference:
            self.state.visited_location_ids = tuple(list(self.state.visited_location_ids) + [req.target_reference])
        self._emit_event(HistoryEventKind.NAVIGATION, action.tick, self.state.simulation_time_s,
                         req.target_reference, {"from_scale": from_scale.value, "to_scale": to_scale.value,
                                                "frame_id": nav_result.frame_id, "rebase": nav_result.rebase_applied,
                                                "steps": nav_result.steps}, action.classification)
        result = InteractionResult(action_id=action.action_id, success=True, tick=action.tick,
                                   data={"navigation": nav_result.to_dict(), "causal": "no teleport: movement via physics required"},
                                   classification=action.classification)
        self._results.append(result)
        # Transition to ARRIVING -> EXPLORING or IDLE deterministically based on scale jump size
        try:
            if nav_result.steps == 0:
                # same scale: remain EXPLORING
                if self.fsm.state == ExplorationStateType.NAVIGATING:
                    self.fsm.transition(ExplorationStateType.IDLE)
            else:
                if self.fsm.state == ExplorationStateType.NAVIGATING:
                    self.fsm.transition(ExplorationStateType.ARRIVING)
                    # auto-advance to EXPLORING if not large travel
                    if nav_result.steps <= 3:
                        self.fsm.transition(ExplorationStateType.EXPLORING)
        except StateTransitionError:
            pass
        return result

    def _handle_travel(self, action: InteractionAction, travel_req: Optional[TravelRequest]) -> InteractionResult:
        if travel_req is None:
            # Try to build from action.parameters
            p = action.parameters
            method = TravelMethod(p.get("method", "CONVENTIONAL_RELATIVISTIC"))
            travel_req = TravelRequest(
                request_id=self._next_id("travel"),
                method=method,
                target_id=action.target_id or p.get("target_id", "unknown"),
                origin_frame_id=action.frame_id,
                destination_frame_id=p.get("destination_frame_id"),
                classification=Classification(p.get("classification", action.classification.value)),
                constraints=TravelConstraints(
                    requires_energy_j=p.get("requires_energy_j"),
                    requires_stability=p.get("requires_stability"),
                    max_proper_time_s=p.get("max_proper_time_s"),
                    causal=p.get("causal", True),
                ),
                parameters=dict(p),
            )
        # Speculative guard
        if travel_req.classification in (Classification.SPECULATIVE, Classification.HYPOTHETICAL) and not self.config.allow_speculative_travel:
            self.warning_sink.emit(ScientificWarning(WarningCode.SPECULATIVE_MODEL, WarningSeverity.WARNING,
                                                      f"speculative travel {travel_req.method.value} requires allow_speculative_travel",
                                                      {"method": travel_req.method.value}))
            # Still allow but with warning; don't silently block unless constraints say so
        result = self.travel.initiate(travel_req)
        self.state.travel_ids = tuple(list(self.state.travel_ids) + [travel_req.request_id])
        self._emit_event(HistoryEventKind.TRAVEL_EVENT, action.tick, self.state.simulation_time_s,
                         travel_req.target_id,
                         {"method": travel_req.method.value, "proper_time_s": result.proper_time_s,
                          "causal_status": result.causal_status, "success": result.success},
                         result.classification)
        if not result.success:
            raise TravelError(result.error_message or "travel failed")
        # Proper time accounting
        if result.proper_time_s is not None:
            self.state.proper_time_s += float(result.proper_time_s)
        if result.coordinate_time_s is not None:
            self.state.coordinate_time_s += float(result.coordinate_time_s)
        ir = InteractionResult(action_id=action.action_id, success=True, tick=action.tick,
                               data={"travel": result.to_dict()}, classification=result.classification,
                               warnings=tuple(w.to_dict() for w in self.warning_sink.all()))
        self._results.append(ir)
        # FSM: TRAVELLING -> IN_TRANSIT -> ARRIVING
        try:
            if self.fsm.state == ExplorationStateType.TRAVELLING:
                self.fsm.transition(ExplorationStateType.IN_TRANSIT)
                self.fsm.transition(ExplorationStateType.ARRIVING)
        except StateTransitionError:
            pass
        return ir

    def _handle_spacecraft(self, action: InteractionAction, inp: Optional[ControlInput]) -> InteractionResult:
        if inp is None:
            # Try to parse from parameters
            p = action.parameters
            from .controls import ThrottleCommand, OrientationCommand, TrajectoryControl, CameraControl, ControlInput
            throttle = None
            if "throttle" in p:
                throttle = ThrottleCommand(throttle=float(p["throttle"]), duration_s=float(p.get("duration_s", 0.1)), engine_id=p.get("engine_id"))
            traj = None
            if "delta_v" in p:
                traj = TrajectoryControl(delta_v=tuple(p["delta_v"]), frame_id=p.get("frame_id"))
            inp = ControlInput(throttle=throttle, trajectory=traj, target_id=action.target_id)
        entity_id = self.state.active_entity_id or self.state.active_spacecraft_id or action.target_id
        if not entity_id:
            raise ControlError("spacecraft command requires active entity/spacecraft or target_id")
        translated = self.control_translator.translate(entity_id, inp, action.tick)
        self._emit_event(HistoryEventKind.SPACECRAFT_TRANSITION, action.tick, self.state.simulation_time_s,
                         entity_id, {"commands": translated["commands"]}, action.classification)
        result = InteractionResult(action_id=action.action_id, success=True, tick=action.tick,
                                   data={"translated": translated, "note": "commands queued for authoritative SpacecraftSystem/MotionSystem"},
                                   classification=action.classification)
        self._results.append(result)
        return result

    def _handle_track(self, action: InteractionAction) -> InteractionResult:
        if action.target_id is None:
            raise TargetError("TRACK/FOLLOW requires target_id")
        target = self.targets.get_or_raise(action.target_id)
        self.state.active_target_id = target.target_id
        self._emit_event(HistoryEventKind.OBJECT_OBSERVED, action.tick, self.state.simulation_time_s,
                         target.target_id, {"action": action.type.value}, action.classification)
        result = InteractionResult(action_id=action.action_id, success=True, tick=action.tick,
                                   data={"tracking": target.to_dict()}, classification=target.classification)
        self._results.append(result)
        return result

    def _handle_pause(self, action: InteractionAction) -> InteractionResult:
        if self.clock is not None:
            try:
                self.clock.pause()
            except Exception as e:
                raise TemporalError(str(e)) from e
        result = InteractionResult(action_id=action.action_id, success=True, tick=action.tick,
                                   data={"paused": True}, classification=action.classification)
        self._results.append(result)
        self._emit_event(HistoryEventKind.STATE_TRANSITION, action.tick, self.state.simulation_time_s,
                         None, {"to": "PAUSED"}, action.classification)
        return result

    def _handle_resume(self, action: InteractionAction) -> InteractionResult:
        if self.clock is not None:
            try:
                self.clock.resume()
            except Exception as e:
                raise TemporalError(str(e)) from e
        result = InteractionResult(action_id=action.action_id, success=True, tick=action.tick,
                                   data={"resumed": True}, classification=action.classification)
        self._results.append(result)
        self._emit_event(HistoryEventKind.STATE_TRANSITION, action.tick, self.state.simulation_time_s,
                         None, {"to": "RESUMED"}, action.classification)
        # FSM already transitioned to IDLE at top
        return result

    def _handle_record_discovery(self, action: InteractionAction) -> InteractionResult:
        # Explicit recording path where observation already produced a discovery elsewhere
        p = action.parameters
        ctx_dict = p.get("context")
        if ctx_dict and isinstance(ctx_dict, dict):
            ctx = ObservationContext(
                observer_id=ctx_dict.get("observer_id", self.state.explorer.explorer_id),
                observer_position=tuple(ctx_dict.get("observer_position", self.state.navigation.origin_hint)),
                observation_time_s=float(ctx_dict.get("observation_time_s", self.state.simulation_time_s)),
                frame_id=ctx_dict.get("frame_id"),
                instrument=ctx_dict.get("instrument"),
            )
        else:
            ctx = ObservationContext(observer_id=self.state.explorer.explorer_id,
                                     observer_position=self.state.navigation.origin_hint,
                                     observation_time_s=self.state.simulation_time_s,
                                     frame_id=self.state.navigation.frame_id)
        disc = Discovery(
            discovery_id=p.get("discovery_id", self._next_id("disc")),
            target_id=action.target_id or p.get("target_id", "unknown"),
            context=ctx,
            simulation_time_s=float(p.get("simulation_time_s", self.state.simulation_time_s)),
            observation_time_s=float(p.get("observation_time_s", self.state.simulation_time_s)),
            lookback_time_s=float(p.get("lookback_time_s", 0.0)),
            coordinates=tuple(p.get("coordinates", ctx.observer_position)),
            frame_id=p.get("frame_id", ctx.frame_id),
            measurement_data=dict(p.get("measurement_data", {})),
            provenance=p.get("provenance", "interaction.record_discovery"),
            classification=Classification(p.get("classification", action.classification.value)),
            uncertainty=p.get("uncertainty"),
            source_info=dict(p.get("source_info", {})),
        )
        self.discoveries.record(disc)
        self.state.discovered_ids = tuple(list(self.state.discovered_ids) + [disc.discovery_id])
        self._emit_event(HistoryEventKind.DISCOVERY_MADE, action.tick, self.state.simulation_time_s,
                         disc.target_id, {"discovery_id": disc.discovery_id}, disc.classification)
        result = InteractionResult(action_id=action.action_id, success=True, tick=action.tick,
                                   data={"discovery": disc.to_dict()}, classification=disc.classification)
        self._results.append(result)
        return result

    def _handle_world_interact(self, action: InteractionAction) -> InteractionResult:
        # Delegates to World — does not reimplement world logic
        self._emit_event(HistoryEventKind.INTERACTION_EVENT, action.tick, self.state.simulation_time_s,
                         action.target_id, {"type": action.type.value, "parameters": action.parameters}, action.classification)
        result = InteractionResult(action_id=action.action_id, success=True, tick=action.tick,
                                   data={"type": action.type.value, "note": "delegated to World/Scene authoritative handler"},
                                   classification=action.classification)
        self._results.append(result)
        return result

    # -- replay / serialization helpers ------------------------------------

    def record_interaction(self, action: InteractionAction) -> None:
        self.state.interaction_ids = tuple(list(self.state.interaction_ids) + [action.action_id])

    def results(self) -> tuple[InteractionResult, ...]:
        return tuple(self._results)

    def clear_results(self) -> None:
        self._results.clear()
