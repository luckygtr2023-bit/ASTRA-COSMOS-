"""ASTRA Evolution — serialization (round-trip safe).

Every quantity, state and event can be serialized to plain Python
primitives and reconstructed identically.  Round-trip invariant:

    to_dict → from_dict → to_dict  yields equal dicts.

No NumPy, no binary blobs, no hidden state.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .errors import EvolutionValidationError
from .provenance import Provenance, Quantity
from .state import EvolutionEvent, EvolutionEventKind, EvolutionState


# ---------------------------------------------------------------------------
# Quantity
# ---------------------------------------------------------------------------

def quantity_to_dict(q: Quantity) -> Dict[str, Any]:
    return {
        "value": q.value,
        "unit": q.unit,
        "provenance": q.provenance.value,
        "uncertainty": q.uncertainty,
        "model_id": q.model_id,
        "note": q.note,
    }


def quantity_from_dict(d: Dict[str, Any]) -> Quantity:
    return Quantity(
        value=float(d["value"]),
        unit=d["unit"],
        provenance=Provenance(d["provenance"]),
        uncertainty=float(d["uncertainty"]) if d.get("uncertainty") is not None else None,
        model_id=d.get("model_id"),
        note=d.get("note"),
    )


# ---------------------------------------------------------------------------
# EvolutionState
# ---------------------------------------------------------------------------

def state_to_dict(s: EvolutionState) -> Dict[str, Any]:
    return {
        "object_id": s.object_id,
        "cosmic_time_gyr": s.cosmic_time_gyr,
        "phase": s.phase,
        "model_id": s.model_id,
        "provenance": s.provenance.value,
        "quantities": {k: quantity_to_dict(v) for k, v in s.quantities.items()},
        "metadata": dict(s.metadata),
    }


def state_from_dict(d: Dict[str, Any]) -> EvolutionState:
    return EvolutionState(
        object_id=d["object_id"],
        cosmic_time_gyr=float(d["cosmic_time_gyr"]),
        phase=d["phase"],
        model_id=d["model_id"],
        provenance=Provenance(d["provenance"]),
        quantities={k: quantity_from_dict(v) for k, v in d.get("quantities", {}).items()},
        metadata=dict(d.get("metadata", {})),
    )


# ---------------------------------------------------------------------------
# EvolutionEvent
# ---------------------------------------------------------------------------

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
        "metadata": dict(e.metadata),
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
        provenance=Provenance(d["provenance"]),
        causal_parent_event_id=d.get("causal_parent_event_id"),
        metadata=dict(d.get("metadata", {})),
    )


# ---------------------------------------------------------------------------
# Histories
# ---------------------------------------------------------------------------

def sfh_to_dict(sfh) -> Dict[str, Any]:
    from .state import StarFormationHistory
    if not isinstance(sfh, StarFormationHistory):
        raise TypeError("expected StarFormationHistory")
    return dict(
        object_id=sfh.object_id,
        samples=[list(s) for s in sfh.samples],
        model_id=sfh.model_id,
        provenance=sfh.provenance.value,
    )


def sfh_from_dict(d: Dict[str, Any]):
    from .state import StarFormationHistory
    return StarFormationHistory(
        object_id=d["object_id"],
        samples=tuple(tuple(s) for s in d["samples"]),
        model_id=d["model_id"],
        provenance=Provenance(d["provenance"]),
    )


def metallicity_history_to_dict(mh) -> Dict[str, Any]:
    from .state import MetallicityHistory
    if not isinstance(mh, MetallicityHistory):
        raise TypeError("expected MetallicityHistory")
    return dict(
        object_id=mh.object_id,
        samples=[list(s) for s in mh.samples],
        model_id=mh.model_id,
        provenance=mh.provenance.value,
    )


def metallicity_history_from_dict(d: Dict[str, Any]):
    from .state import MetallicityHistory
    return MetallicityHistory(
        object_id=d["object_id"],
        samples=tuple(tuple(s) for s in d["samples"]),
        model_id=d["model_id"],
        provenance=Provenance(d["provenance"]),
    )


def population_to_dict(ps) -> Dict[str, Any]:
    from .state import PopulationState
    if not isinstance(ps, PopulationState):
        raise TypeError("expected PopulationState")
    return dict(
        population_id=ps.population_id,
        cosmic_time_gyr=ps.cosmic_time_gyr,
        parent_object_id=ps.parent_object_id,
        mass_function=[list(p) for p in ps.mass_function],
        age_distribution=[list(p) for p in ps.age_distribution],
        remnant_fraction=ps.remnant_fraction,
        metallicity=ps.metallicity,
        model_id=ps.model_id,
        provenance=ps.provenance.value,
    )


def population_from_dict(d: Dict[str, Any]):
    from .state import PopulationState
    return PopulationState(
        population_id=d["population_id"],
        cosmic_time_gyr=float(d["cosmic_time_gyr"]),
        parent_object_id=d["parent_object_id"],
        mass_function=tuple(tuple(p) for p in d["mass_function"]),
        age_distribution=tuple(tuple(p) for p in d["age_distribution"]),
        remnant_fraction=float(d["remnant_fraction"]),
        metallicity=float(d["metallicity"]),
        model_id=d["model_id"],
        provenance=Provenance(d["provenance"]),
    )
