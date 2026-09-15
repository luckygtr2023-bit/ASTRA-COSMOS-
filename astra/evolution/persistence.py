"""ASTRA COSMOS — Phase 21: persistence (plain-primitive dict round trips).

Repository convention (see astra.temporal.state, astra.blackhole): state
serializes to plain, JSON-compatible dictionaries; schema carries units
implicitly through documented field names; round-trip
``to_dict -> from_dict -> to_dict`` yields equal dicts.

The model registry serializes its METADATA only; step callables are code
and are re-registered on load (``register_builtin_models`` or custom
registration). This is documented, deliberate: no code ever travels
through a snapshot.
"""
from __future__ import annotations

from typing import Any, Dict, List

from astra.celestial.provenance import DataProvenance

from .errors import EvolutionValidationError
from .events import EvolutionEvent, EvolutionEventKind
from .provenance import ProjectionClass
from .quantity import Quantity
from .state import (
    EvolutionState,
    MetallicityHistory,
    PopulationState,
    StarFormationHistory,
)

_KEY_ORDER = (
    "object_id",
    "object_kind",
    "cosmic_time_gyr",
    "phase",
    "model_id",
    "provenance",
    "projection_class",
    "parent_object_ids",
)


def _normalize(value: Any) -> Any:
    """Tuples -> lists recursively so payloads are JSON-serializable."""
    if isinstance(value, dict):
        return {str(k): _normalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise EvolutionValidationError(
        f"metadata value of type {type(value).__name__} is not JSON-serializable"
    )


def quantity_to_dict(q: Quantity) -> Dict[str, Any]:
    return q.to_dict()


def quantity_from_dict(d: Dict[str, Any]) -> Quantity:
    return Quantity.from_dict(d)


def state_to_dict(s: EvolutionState) -> Dict[str, Any]:
    return {
        "object_id": s.object_id,
        "object_kind": s.object_kind,
        "cosmic_time_gyr": s.cosmic_time_gyr,
        "phase": s.phase,
        "model_id": s.model_id,
        "provenance": s.provenance.value,
        "projection_class": s.projection_class.value,
        "parent_object_ids": list(s.parent_object_ids),
        "quantities": {k: quantity_to_dict(v) for k, v in s.quantities.items()},
        "metadata": _normalize(s.metadata),
    }


def state_from_dict(d: Dict[str, Any]) -> EvolutionState:
    return EvolutionState(
        object_id=d["object_id"],
        object_kind=d["object_kind"],
        cosmic_time_gyr=float(d["cosmic_time_gyr"]),
        phase=d["phase"],
        model_id=d["model_id"],
        provenance=DataProvenance(d["provenance"]),
        projection_class=ProjectionClass(d.get("projection_class", "NONE")),
        parent_object_ids=tuple(d.get("parent_object_ids", ())),
        quantities={k: quantity_from_dict(v) for k, v in d.get("quantities", {}).items()},
        metadata=dict(d.get("metadata", {})),
    )


def event_to_dict(e: EvolutionEvent) -> Dict[str, Any]:
    return {
        "event_id": e.event_id,
        "kind": e.kind.value,
        "cosmic_time_gyr": e.cosmic_time_gyr,
        "source_object_ids": list(e.source_object_ids),
        "resulting_object_ids": list(e.resulting_object_ids),
        "physical_cause": e.physical_cause,
        "model_id": e.model_id,
        "provenance": e.provenance.value,
        "causal_parent_event_id": e.causal_parent_event_id,
        "metadata": _normalize(e.metadata),
    }


def event_from_dict(d: Dict[str, Any]) -> EvolutionEvent:
    return EvolutionEvent(
        event_id=d["event_id"],
        kind=EvolutionEventKind(d["kind"]),
        cosmic_time_gyr=float(d["cosmic_time_gyr"]),
        source_object_ids=tuple(d["source_object_ids"]),
        resulting_object_ids=tuple(d["resulting_object_ids"]),
        physical_cause=d["physical_cause"],
        model_id=d["model_id"],
        provenance=DataProvenance(d["provenance"]),
        causal_parent_event_id=d.get("causal_parent_event_id"),
        metadata=dict(d.get("metadata", {})),
    )


def population_state_to_dict(p: PopulationState) -> Dict[str, Any]:
    return {
        "population_id": p.population_id,
        "cosmic_time_gyr": p.cosmic_time_gyr,
        "parent_object_id": p.parent_object_id,
        "mass_function": [list(pair) for pair in p.mass_function],
        "age_distribution": [list(pair) for pair in p.age_distribution],
        "remnant_fraction": p.remnant_fraction,
        "metallicity": p.metallicity,
        "model_id": p.model_id,
        "provenance": p.provenance.value,
    }


def population_state_from_dict(d: Dict[str, Any]) -> PopulationState:
    return PopulationState(
        population_id=d["population_id"],
        cosmic_time_gyr=float(d["cosmic_time_gyr"]),
        parent_object_id=d.get("parent_object_id", ""),
        mass_function=tuple((float(m), float(w)) for m, w in d.get("mass_function", ())),
        age_distribution=tuple((float(a), float(w)) for a, w in d.get("age_distribution", ())),
        remnant_fraction=float(d["remnant_fraction"]),
        metallicity=float(d["metallicity"]),
        model_id=d["model_id"],
        provenance=DataProvenance(d.get("provenance", "SIMULATED_DATA")),
    )


def sfh_to_dict(h: StarFormationHistory) -> Dict[str, Any]:
    return {
        "object_id": h.object_id,
        "samples": [list(pair) for pair in h.samples],
        "model_id": h.model_id,
        "provenance": h.provenance.value,
    }


def sfh_from_dict(d: Dict[str, Any]) -> StarFormationHistory:
    return StarFormationHistory(
        object_id=d["object_id"],
        samples=tuple((float(t), float(s)) for t, s in d.get("samples", ())),
        model_id=d["model_id"],
        provenance=DataProvenance(d.get("provenance", "SIMULATED_DATA")),
    )


def metallicity_history_to_dict(h: MetallicityHistory) -> Dict[str, Any]:
    return {
        "object_id": h.object_id,
        "samples": [list(pair) for pair in h.samples],
        "model_id": h.model_id,
        "provenance": h.provenance.value,
    }


def metallicity_history_from_dict(d: Dict[str, Any]) -> MetallicityHistory:
    return MetallicityHistory(
        object_id=d["object_id"],
        samples=tuple((float(t), float(z)) for t, z in d.get("samples", ())),
        model_id=d["model_id"],
        provenance=DataProvenance(d.get("provenance", "SIMULATED_DATA")),
    )


__all__ = [
    "quantity_to_dict",
    "quantity_from_dict",
    "state_to_dict",
    "state_from_dict",
    "event_to_dict",
    "event_from_dict",
    "population_state_to_dict",
    "population_state_from_dict",
    "sfh_to_dict",
    "sfh_from_dict",
    "metallicity_history_to_dict",
    "metallicity_history_from_dict",
]
