"""ASTRA Interaction — persistence helpers (plain primitives, deterministic)."""

from __future__ import annotations

from typing import Dict, Any

from .state import ExplorationState
from .history import ExplorationHistory
from .target import TargetRegistry
from .observation import DiscoveryRegistry
from .statemachine import ExplorationStateMachine


def state_to_dict(s: ExplorationState) -> Dict[str, Any]:
    return s.to_dict()

def state_from_dict(d: Dict[str, Any]) -> ExplorationState:
    return ExplorationState.from_dict(d)

def history_to_dict(h: ExplorationHistory) -> list:
    return h.to_dict()

def history_from_dict(d: list) -> ExplorationHistory:
    return ExplorationHistory.from_dict(d)

def target_registry_to_dict(r: TargetRegistry) -> list:
    return r.to_dict()

def target_registry_from_dict(d: list) -> TargetRegistry:
    return TargetRegistry.from_dict(d)

def discovery_registry_to_dict(r: DiscoveryRegistry) -> list:
    return r.to_dict()

def discovery_registry_from_dict(d: list) -> DiscoveryRegistry:
    return DiscoveryRegistry.from_dict(d)

def statemachine_to_dict(m: ExplorationStateMachine) -> Dict:
    return m.to_dict()

def statemachine_from_dict(d: Dict) -> ExplorationStateMachine:
    return ExplorationStateMachine.from_dict(d)

def full_snapshot(state: ExplorationState, history: ExplorationHistory,
                  targets: TargetRegistry, discoveries: DiscoveryRegistry,
                  fsm: ExplorationStateMachine) -> Dict[str, Any]:
    return {
        "state": state_to_dict(state),
        "history": history_to_dict(history),
        "targets": target_registry_to_dict(targets),
        "discoveries": discovery_registry_to_dict(discoveries),
        "fsm": statemachine_to_dict(fsm),
        "schema": "astra.interaction.v1",
    }

def full_snapshot_from_dict(d: Dict[str, Any]) -> tuple[ExplorationState, ExplorationHistory, TargetRegistry, DiscoveryRegistry, ExplorationStateMachine]:
    return (
        state_from_dict(d["state"]),
        history_from_dict(d["history"]),
        target_registry_from_dict(d["targets"]),
        discovery_registry_from_dict(d["discoveries"]),
        statemachine_from_dict(d["fsm"]),
    )
