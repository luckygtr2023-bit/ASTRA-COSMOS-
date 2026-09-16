"""ASTRA Scientific — assumption registry (§2.6).

Assumptions live in a repository-wide registry, are identified by stable IDs,
and can be attached to any provenance node or model descriptor. No assumption
may be hidden inside a code path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple

from .errors import ScientificValidationError


@dataclass(frozen=True)
class Assumption:
    """Explicit, stable model assumption."""

    assumption_id: str
    statement: str
    category: str
    parameter_values: Dict[str, float] = field(default_factory=dict)
    notes: str = ""

    def __post_init__(self):
        if not isinstance(self.assumption_id, str) or not self.assumption_id:
            raise ScientificValidationError("assumption_id required: non-empty string")
        if not isinstance(self.statement, str) or not self.statement:
            raise ScientificValidationError("statement must be a non-empty string")
        if not isinstance(self.category, str) or not self.category:
            raise ScientificValidationError("category must be a non-empty string")
        if not isinstance(self.notes, str):
            raise TypeError("notes must be a string")
        object.__setattr__(self, "parameter_values", dict(self.parameter_values))
        for k, v in self.parameter_values.items():
            if not isinstance(k, str) or not k:
                raise ScientificValidationError("parameter_values keys must be non-empty strings")
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ScientificValidationError(f"parameter_values[{k!r}] must be numeric")
            import math
            if math.isnan(float(v)) or math.isinf(float(v)):
                raise ScientificValidationError(f"parameter_values[{k!r}] must be finite")


class AssumptionRegistry:
    """Repository-wide registry of assumptions (stable IDs, deterministic order)."""

    def __init__(self) -> None:
        self._items: Dict[str, Assumption] = {}

    def register(self, a: Assumption) -> None:
        if not isinstance(a, Assumption):
            raise TypeError("a must be an Assumption")
        if a.assumption_id in self._items:
            raise ScientificValidationError(f"duplicate assumption_id {a.assumption_id!r}")
        self._items[a.assumption_id] = a

    def get(self, assumption_id: str) -> Assumption:
        try:
            return self._items[assumption_id]
        except KeyError:
            raise ScientificValidationError(f"unknown assumption {assumption_id!r}")

    def contains(self, assumption_id: str) -> bool:
        return assumption_id in self._items

    def list_ids(self) -> Tuple[str, ...]:
        return tuple(sorted(self._items.keys()))

    def list_assumptions(self) -> Tuple[Assumption, ...]:
        return tuple(self._items[k] for k in sorted(self._items.keys()))

    def __len__(self) -> int:
        return len(self._items)

    def to_dict(self) -> Dict:
        return {aid: {"assumption_id": a.assumption_id, "statement": a.statement,
                       "category": a.category, "parameter_values": dict(a.parameter_values),
                       "notes": a.notes} for aid, a in self._items.items()}
