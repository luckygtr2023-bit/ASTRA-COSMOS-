"""ASTRA Scientific — serialization (plain primitives, deterministic)."""

from __future__ import annotations

from typing import Any, Dict

from .classification import Classification
from .errors import ScientificValidationError
from .provenance import ParameterSource, ProvenanceNode


def node_to_dict(n: ProvenanceNode) -> Dict[str, Any]:
    return {
        "node_id": n.node_id,
        "classification": n.classification.value,
        "source_type": n.source_type,
        "source_id": n.source_id,
        "acquisition_time_utc": n.acquisition_time_utc,
        "model_id": n.model_id,
        "model_version": n.model_version,
        "parent_ids": list(n.parent_ids),
        "assumptions": list(n.assumptions),
        "parameter_sources": {k: v.value for k, v in n.parameter_sources.items()},
        "software_version": n.software_version,
        "metadata": dict(n.metadata),
    }


def node_from_dict(d: Dict[str, Any]) -> ProvenanceNode:
    try:
        return ProvenanceNode(
            node_id=d["node_id"],
            classification=Classification(d["classification"]),
            source_type=d["source_type"],
            source_id=d.get("source_id"),
            acquisition_time_utc=d.get("acquisition_time_utc"),
            model_id=d.get("model_id"),
            model_version=d.get("model_version"),
            parent_ids=tuple(d.get("parent_ids", [])),
            assumptions=tuple(d.get("assumptions", [])),
            parameter_sources={
                k: ParameterSource(v) for k, v in d.get("parameter_sources", {}).items()
            },
            software_version=d.get("software_version"),
            metadata=dict(d.get("metadata", {})),
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise ScientificValidationError(f"failed to deserialize ProvenanceNode: {exc}") from exc


def envelope_to_dict(env) -> Dict[str, Any]:
    from .envelope import ResultEnvelope
    if not isinstance(env, ResultEnvelope):
        raise TypeError("expected ResultEnvelope")
    return {
        "envelope_id": env.envelope_id,
        "classification": env.classification.value,
        "provenance": env.provenance.node_id if env.provenance else None,
        "model_id": env.model_id,
        "valid": env.valid,
        "assumption_ids": list(env.assumption_ids),
        "warnings": [w.to_dict() for w in env.warnings],
        "reproducibility": dict(env.reproducibility),
        "metadata": dict(env.metadata),
        "value": env.value,
    }


def envelope_from_dict(d: Dict[str, Any]):
    from .classification import Classification as Cl
    from .envelope import ResultEnvelope
    from .provenance import ProvenanceRef
    from .warnings import ScientificWarning
    return ResultEnvelope(
        envelope_id=d["envelope_id"],
        value=d.get("value"),
        classification=Cl(d["classification"]),
        provenance=ProvenanceRef(d["provenance"]) if d.get("provenance") else None,
        assumption_ids=tuple(d.get("assumption_ids", [])),
        model_id=d.get("model_id"),
        valid=d.get("valid"),
        warnings=tuple(ScientificWarning.from_dict(w) for w in d.get("warnings", [])),
        reproducibility=dict(d.get("reproducibility", {})),
        metadata=dict(d.get("metadata", {})),
    )
