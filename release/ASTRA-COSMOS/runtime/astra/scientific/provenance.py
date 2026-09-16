"""ASTRA Scientific — provenance nodes and derivation chains.

Append-only (§2.5, §2.33).  A derivation creates a NEW node; upstream nodes
are never mutated.  Chains are walkable back to roots, references avoid
copying large state.

Provenance references state; it does not copy it (cf. §2.4).

Generation timestamps are metadata only — never simulation state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Tuple

from .classification import Classification
from .errors import ScientificProvenanceError


class ParameterSource(str, Enum):
    """Origin of a parameter (§2.23). No undocumented magic number may become truth."""

    OBSERVATIONAL_DATASET = "OBSERVATIONAL_DATASET"
    CONFIGURED_CONSTANT = "CONFIGURED_CONSTANT"
    DERIVED_VALUE = "DERIVED_VALUE"
    USER_INPUT = "USER_INPUT"
    MODEL_DEFAULT = "MODEL_DEFAULT"
    THEORETICAL_ASSUMPTION = "THEORETICAL_ASSUMPTION"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ProvenanceRef:
    """Lightweight reference to a provenance node (for hot paths)."""

    node_id: str

    def __post_init__(self):
        if not isinstance(self.node_id, str) or not self.node_id:
            raise ScientificProvenanceError("node_id must be a non-empty string")


@dataclass(frozen=True)
class ProvenanceNode:
    """Immutable provenance node (§2.4).

    Fields mirror §2.4 where applicable; large data is referenced via IDs,
    not copied.  The node is append-only; downstream derivations create new
    nodes that list this node's id in ``parent_ids``.
    """

    node_id: str
    classification: Classification
    source_type: str
    source_id: Optional[str] = None
    acquisition_time_utc: Optional[str] = None  # metadata only, never sim state
    model_id: Optional[str] = None
    model_version: Optional[str] = None
    parent_ids: Tuple[str, ...] = ()
    assumptions: Tuple[str, ...] = ()
    parameter_sources: Dict[str, ParameterSource] = field(default_factory=dict)
    software_version: Optional[str] = None
    metadata: Dict[str, object] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.node_id, str) or not self.node_id:
            raise ScientificProvenanceError("node_id required: non-empty string")
        if not isinstance(self.classification, Classification):
            raise TypeError("classification must be a Classification")
        if not isinstance(self.source_type, str) or not self.source_type:
            raise ScientificProvenanceError("source_type must be a non-empty string")
        # Normalize tuples/dicts to immutable forms
        object.__setattr__(self, "parent_ids", tuple(self.parent_ids))
        object.__setattr__(self, "assumptions", tuple(self.assumptions))
        object.__setattr__(self, "parameter_sources", dict(self.parameter_sources))
        object.__setattr__(self, "metadata", dict(self.metadata))
        for pid in self.parent_ids:
            if not isinstance(pid, str) or not pid:
                raise ScientificProvenanceError("parent_ids must be non-empty strings")
        for aid in self.assumptions:
            if not isinstance(aid, str) or not aid:
                raise ScientificProvenanceError("assumptions must be non-empty strings")
        for k, v in self.parameter_sources.items():
            if not isinstance(k, str) or not k:
                raise ScientificProvenanceError("parameter_sources keys must be non-empty strings")
            if not isinstance(v, ParameterSource):
                raise TypeError(f"parameter_sources[{k!r}] must be a ParameterSource")


class DerivationChain:
    """Walkable, append-only derivation chain.

    The chain is deterministic: ancestors are visited BFS from the queried
    node; results are sorted by depth then node_id for reproducibility.
    """

    def __init__(self) -> None:
        self._nodes: Dict[str, ProvenanceNode] = {}

    def add(self, node: ProvenanceNode) -> None:
        """Add a node; validates parent existence and duplicate id."""
        if not isinstance(node, ProvenanceNode):
            raise TypeError("node must be a ProvenanceNode")
        if node.node_id in self._nodes:
            raise ScientificProvenanceError(f"duplicate node_id {node.node_id!r}")
        for pid in node.parent_ids:
            if pid not in self._nodes:
                raise ScientificProvenanceError(f"unknown parent {pid!r} for node {node.node_id!r}")
        self._nodes[node.node_id] = node

    def get(self, node_id: str) -> ProvenanceNode:
        try:
            return self._nodes[node_id]
        except KeyError:
            raise ScientificProvenanceError(f"unknown node_id {node_id!r}")

    def contains(self, node_id: str) -> bool:
        return node_id in self._nodes

    def ancestors(self, node_id: str) -> Tuple[str, ...]:
        """Deterministic BFS back to roots, excluding the queried node itself.

        Returns ancestor ids sorted by (depth, node_id) where depth is
        graph distance from the start node.  This ordering is stable across
        runs and does not depend on insertion order.
        """
        if node_id not in self._nodes:
            raise ScientificProvenanceError(f"unknown node_id {node_id!r}")
        seen: set[str] = set()
        frontier: list[tuple[str, int]] = [(node_id, 0)]
        # Collect (depth, node_id) for all reachable ancestors
        collected: list[tuple[int, str]] = []
        # BFS
        idx = 0
        seen.add(node_id)
        queue = [(node_id, 0)]
        while idx < len(queue):
            cur, depth = queue[idx]
            idx += 1
            for pid in self._nodes[cur].parent_ids:
                if pid in seen:
                    continue
                seen.add(pid)
                collected.append((depth + 1, pid))
                queue.append((pid, depth + 1))
        collected.sort()
        return tuple(nid for _, nid in collected)

    def root_classifications(self, node_id: str) -> Tuple[Classification, ...]:
        """Classifications of all ancestors, in deterministic ancestor order."""
        return tuple(self.get(nid).classification for nid in self.ancestors(node_id))

    def lineage(self, node_id: str) -> Tuple[ProvenanceNode, ...]:
        """Full lineage (ancestors + self) in BFS order."""
        anc = self.ancestors(node_id)
        return tuple(self.get(nid) for nid in (*anc, node_id))

    def node_count(self) -> int:
        return len(self._nodes)

    def to_dict(self) -> Dict:
        return {nid: _node_to_dict(n) for nid, n in self._nodes.items()}

    @classmethod
    def from_dict(cls, data: Dict) -> "DerivationChain":
        chain = cls()
        # Add in topological order (parents before children); data is already dict
        # We need to add nodes sorted by ancestor depth to satisfy parent checks.
        # Simplest: repeatedly try to add pending nodes.
        pending = dict(data)
        # First deserialize all nodes without parent checks, then add in order
        nodes = {nid: _node_from_dict(d) for nid, d in pending.items()}
        # Topological insertion: sort by number of ancestors (heuristic)
        # Use insertion order based on parent closure size
        remaining = set(nodes.keys())
        added = set()
        while remaining:
            progress = False
            for nid in sorted(remaining):
                node = nodes[nid]
                if all(pid in added for pid in node.parent_ids):
                    chain._nodes[nid] = node
                    added.add(nid)
                    remaining.remove(nid)
                    progress = True
                    break
            if not progress:
                raise ScientificProvenanceError(f"circular or missing parents among {sorted(remaining)}")
        return chain


def _node_to_dict(n: ProvenanceNode) -> Dict:
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


def _node_from_dict(d: Dict) -> ProvenanceNode:
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
        parameter_sources={k: ParameterSource(v) for k, v in d.get("parameter_sources", {}).items()},
        software_version=d.get("software_version"),
        metadata=dict(d.get("metadata", {})),
    )
