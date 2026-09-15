"""ASTRA Celestial - system hierarchy and relationship graphs.

Contract: parent-child structure ("Moon belongs to Earth") is explicitly
SEPARATE from orbital mechanics ("Moon's current Keplerian elements",
owned by astra.orbital). This module is pure structure:

    - STRICT DAG: HierarchyNode.add_child refuses any edge that would
      create a cycle (direct, via-parent, or self-edge) with
      CyclicHierarchyError - mass aggregation can then never recurse
      forever and "A orbits B while B orbits A" is unrepresentable.
    - Duplicate attachments are rejected (DuplicateNodeError).
    - Mass aggregation sums the subtree and HONESTLY FAILS with
      IncompletePhysicalDataError if ANY member's mass is unknown -
      no zeros, no guesses (barycenter computation itself remains in
      astra.nbody.barycenter; this layer only counts).
    - Deterministic iteration: children are kept in insertion order.
"""

from __future__ import annotations

from typing import Optional, Tuple

from astra.celestial.exceptions import (
    CyclicHierarchyError,
    DuplicateNodeError,
    IncompletePhysicalDataError,
)
from astra.celestial.identity import CelestialIdentity


class HierarchyNode:
    """A node in the celestial-system DAG (identity + children links)."""

    __slots__ = ("_identity", "_parent", "_children", "_properties")

    def __init__(self, identity: CelestialIdentity,
                 parent: Optional["HierarchyNode"] = None):
        if not isinstance(identity, CelestialIdentity):
            raise TypeError("identity must be a CelestialIdentity")
        self._identity = identity
        self._parent: Optional["HierarchyNode"] = None
        self._children: Tuple["HierarchyNode", ...] = ()
        self._properties = None
        if parent is not None:
            parent.add_child(self)

    @property
    def identity(self) -> CelestialIdentity:
        return self._identity

    @property
    def parent(self) -> Optional["HierarchyNode"]:
        return self._parent

    @property
    def children(self) -> Tuple["HierarchyNode", ...]:
        return self._children

    @property
    def object_id(self) -> str:
        return self._identity.object_id

    # -- structure mutation (cycle-safe) ------------------------------------
    def _ancestors(self) -> Tuple["HierarchyNode", ...]:
        chain = []
        node = self._parent
        while node is not None:
            chain.append(node)
            node = node._parent
        return tuple(chain)

    def add_child(self, child: "HierarchyNode") -> "HierarchyNode":
        """Attach a child, enforcing the DAG invariant.

        Raises:
            CyclicHierarchyError: if child is self, is an ancestor of self,
                or already has a parent (re-parenting must be explicit).
            DuplicateNodeError: if child's identity already hangs below self.
        """
        if not isinstance(child, HierarchyNode):
            raise TypeError("child must be a HierarchyNode")
        if child is self:
            raise CyclicHierarchyError("a node cannot be its own child")
        if child._parent is not None:
            raise CyclicHierarchyError(
                f"{child.identity.canonical_name!r} already has a parent; "
                "detaching first keeps the graph an explicit DAG"
            )
        if child.object_id in (a.object_id for a in self._ancestors()):
            raise CyclicHierarchyError(
                f"edge {self.identity.canonical_name!r} -> "
                f"{child.identity.canonical_name!r} would create a cycle "
                "(child is an ancestor)"
            )
        self._children = self._children + (child,)
        child._parent = self
        return child

    def remove_child(self, child: "HierarchyNode") -> None:
        if child not in self._children:
            raise ValueError(
                f"{child.identity.canonical_name!r} is not a child of "
                f"{self.identity.canonical_name!r}"
            )
        self._children = tuple(c for c in self._children if c is not child)
        child._parent = None

    def _subtree(self) -> Tuple["HierarchyNode", ...]:
        out = [self]
        for c in self._children:
            out.extend(c._subtree())
        return tuple(out)

    # -- queries -------------------------------------------------------------
    def path_to_root(self) -> Tuple["HierarchyNode", ...]:
        """(self, parent, grandparent, ...) up to the root."""
        return (self,) + self._ancestors()

    def root(self) -> "HierarchyNode":
        node = self
        while node._parent is not None:
            node = node._parent
        return node

    def total_system_mass_kg(self) -> float:
        """Sum of masses over the subtree (kg).

        Raises IncompletePhysicalDataError if ANY member mass is unknown:
        a partial total is never returned (no zero-filling).
        """
        total = 0.0
        for node in self._subtree():
            props = node.properties_block
            if props is None or props.mass_kg is None:
                raise IncompletePhysicalDataError(
                    f"mass of {node.identity.canonical_name!r} is UNKNOWN; "
                    "refusing to return a partial system mass"
                )
            total += props.mass_kg
        return total

    # -- attached definition (optional, set by domain objects) ---------------
    @property
    def properties_block(self):
        """The attached CelestialProperties, if the builder supplied one."""
        return getattr(self, "_properties", None)

    def attach_properties(self, properties) -> None:
        """Attach the (immutable) property block for mass aggregation."""
        from astra.celestial.properties import CelestialProperties
        if not isinstance(properties, CelestialProperties):
            raise TypeError("properties must be a CelestialProperties")
        self._properties = properties  # noqa: B010 - slot defined below
