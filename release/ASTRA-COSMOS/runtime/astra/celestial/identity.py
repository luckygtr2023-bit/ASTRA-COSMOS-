"""ASTRA Celestial - catalog-agnostic identity.

Contract: a celestial object's identity is separable from its physics.
Identities are immutable, carry any number of catalog aliases, and are
deterministic: the same canonical name ALWAYS yields the same object id
(no UUIDs, no RNG). Deterministic ids keep simulations reproducible and
save files stable across runs.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Dict, Mapping, Tuple

from astra.celestial.exceptions import DuplicateNodeError


@dataclass(frozen=True)
class CelestialIdentity:
    """Immutable, catalog-agnostic celestial identity.

    canonical_name: the ASTRA-internal unique name (non-empty).
    catalog_aliases: (catalog, designation) pairs, e.g.
        (("HIP", "8102"), ("BD+", "5428")). Stored as a tuple so the
        identity stays hashable and exactly reproducible; exposed as a
        read-only mapping via :attr:`alias_map`.
    object_id: deterministic identifier derived from the canonical name
        (sha256 prefix) when not supplied.
    """

    canonical_name: str
    catalog_aliases: Tuple[Tuple[str, str], ...] = field(default=())
    object_id: str = ""  # derived deterministically when empty

    def __post_init__(self):
        if not isinstance(self.canonical_name, str) or not self.canonical_name.strip():
            raise ValueError("canonical_name must be a non-empty string")
        for alias in self.catalog_aliases:
            catalog, designation = alias
            if not isinstance(catalog, str) or not catalog.strip():
                raise ValueError(f"catalog label must be a non-empty string: {alias!r}")
            if not isinstance(designation, str) or not designation.strip():
                raise ValueError(f"catalog designation must be non-empty: {alias!r}")
        if not self.object_id:
            object.__setattr__(self, "object_id", self._derive_id())

    def _derive_id(self) -> str:
        digest = hashlib.sha256(
            self.canonical_name.strip().encode("utf-8")
        ).hexdigest()
        return f"ASTRA-{digest[:16]}"

    @property
    def alias_map(self) -> Mapping[str, str]:
        """Read-only {catalog: designation} view of the aliases."""
        return MappingProxyType(dict(self.catalog_aliases))

    def designation_in(self, catalog: str) -> str | None:
        """Alias in the given catalog, or None (never a guess)."""
        return self.alias_map.get(catalog)

    def with_alias(self, catalog: str, designation: str) -> "CelestialIdentity":
        """Return a NEW identity with the alias added/replaced
        (immutability: the original is never modified)."""
        if not isinstance(catalog, str) or not catalog.strip():
            raise ValueError("catalog label must be a non-empty string")
        if not isinstance(designation, str) or not designation.strip():
            raise ValueError("designation must be a non-empty string")
        kept = tuple(
            (c, d) for c, d in self.catalog_aliases if c != catalog
        )
        return replace(self, catalog_aliases=kept + ((catalog, designation),))

    def to_dict(self) -> Dict[str, str]:
        return {
            "canonical_name": self.canonical_name,
            "catalog_aliases": [list(a) for a in self.catalog_aliases],
            "object_id": self.object_id,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "CelestialIdentity":
        return cls(
            canonical_name=data["canonical_name"],
            catalog_aliases=tuple(tuple(a) for a in data.get("catalog_aliases", ())),
            object_id=data.get("object_id", ""),
        )


def ensure_distinct(*identities: CelestialIdentity) -> None:
    """Raise DuplicateNodeError when the same identity appears twice."""
    seen = set()
    for identity in identities:
        if identity.object_id in seen:
            raise DuplicateNodeError(
                f"duplicate celestial identity: {identity.canonical_name!r} "
                f"({identity.object_id})"
            )
        seen.add(identity.object_id)
