"""ASTRA Scientific — audit trail (§2.27).

Append-only, reference-based (never copies large datasets).  Deterministic
ordering.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple


@dataclass(frozen=True)
class AuditEntry:
    """Single audit entry: operation that created a provenance node."""

    entry_id: str
    node_id: str
    operation: str
    inputs: Tuple[str, ...] = ()
    outputs: Tuple[str, ...] = ()
    metadata: Dict[str, object] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.entry_id, str) or not self.entry_id:
            raise ValueError("entry_id must be a non-empty string")
        if not isinstance(self.node_id, str) or not self.node_id:
            raise ValueError("node_id must be a non-empty string")
        if not isinstance(self.operation, str) or not self.operation:
            raise ValueError("operation must be a non-empty string")
        object.__setattr__(self, "inputs", tuple(self.inputs))
        object.__setattr__(self, "outputs", tuple(self.outputs))
        object.__setattr__(self, "metadata", dict(self.metadata))


class AuditTrail:
    """Append-only audit trail (references, not copies)."""

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    def append(self, e: AuditEntry) -> None:
        if not isinstance(e, AuditEntry):
            raise TypeError("e must be an AuditEntry")
        # Enforce append-only duplicate check
        if any(entry.entry_id == e.entry_id for entry in self._entries):
            raise ValueError(f"duplicate entry_id {e.entry_id!r}")
        self._entries.append(e)

    def for_node(self, node_id: str) -> Tuple[AuditEntry, ...]:
        return tuple(e for e in self._entries if e.node_id == node_id)

    def for_operation(self, operation: str) -> Tuple[AuditEntry, ...]:
        return tuple(e for e in self._entries if e.operation == operation)

    def all_entries(self) -> Tuple[AuditEntry, ...]:
        return tuple(self._entries)

    def count(self) -> int:
        return len(self._entries)

    def clear(self) -> None:
        self._entries.clear()

    def to_dict(self) -> list[Dict]:
        return [{"entry_id": e.entry_id, "node_id": e.node_id, "operation": e.operation,
                 "inputs": list(e.inputs), "outputs": list(e.outputs), "metadata": dict(e.metadata)}
                for e in self._entries]
