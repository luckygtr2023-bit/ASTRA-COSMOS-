"""Hierarchy DAG tests: cycles, aggregation honesty, traversal."""
import pytest

from astra.celestial import (
    CyclicHierarchyError,
    DataProvenance,
    DuplicateNodeError,
    HierarchyNode,
    IncompletePhysicalDataError,
    create_identity,
    create_properties,
)


def _node(name, mass=None):
    node = HierarchyNode(create_identity(name))
    if mass is not None:
        node.attach_properties(
            create_properties(DataProvenance.REAL_DATA, mass_kg=mass))
    return node


class TestStructure:
    def test_parent_child_linkage(self):
        root = _node("Sun", 1.989e30)
        earth = _node("Earth", 5.972e24)
        root.add_child(earth)
        assert earth.parent is root
        assert root.children == (earth,)
        assert root.root() is root
        assert earth.root() is root

    def test_path_to_root(self):
        root = _node("Sun", 1.0e30)
        earth = _node("Earth", 1.0e24)
        moon = _node("Moon", 1.0e22)
        root.add_child(earth)
        earth.add_child(moon)
        assert [n.identity.canonical_name for n in moon.path_to_root()] == [
            "Moon", "Earth", "Sun"
        ]

    def test_children_kept_in_insertion_order(self):
        root = _node("Sun", 1.0e30)
        for name in ("Mercury", "Venus", "Earth", "Mars"):
            root.add_child(_node(name, 1.0e23))
        assert [c.identity.canonical_name for c in root.children] == [
            "Mercury", "Venus", "Earth", "Mars"
        ]

    def test_detach(self):
        root = _node("Sun", 1.0e30)
        earth = _node("Earth", 1.0e24)
        root.add_child(earth)
        root.remove_child(earth)
        assert earth.parent is None and root.children == ()
        # Detached node can be re-attached elsewhere (DAG preserved).
        other = _node("AlphaCen", 1.0e30)
        other.add_child(earth)
        assert earth.parent is other


class TestDAGEnforcement:
    def test_self_edge_rejected(self):
        a = _node("A", 1.0)
        with pytest.raises(CyclicHierarchyError):
            a.add_child(a)

    def test_direct_cycle_rejected(self):
        a = _node("A", 1.0)
        b = _node("B", 1.0)
        a.add_child(b)
        with pytest.raises(CyclicHierarchyError):
            b.add_child(a)

    def test_grandparent_cycle_rejected(self):
        a = _node("A", 1.0)
        b = _node("B", 1.0)
        c = _node("C", 1.0)
        a.add_child(b)
        b.add_child(c)
        with pytest.raises(CyclicHierarchyError):
            c.add_child(a)  # A is C's grandparent

    def test_reparenting_requires_explicit_detach(self):
        a = _node("A", 1.0)
        b = _node("B", 1.0)
        child = _node("Child", 1.0)
        a.add_child(child)
        with pytest.raises(CyclicHierarchyError):
            b.add_child(child)

    def test_duplicate_subtree_attachment_rejected(self):
        # An attached node carries a parent: re-attachment is refused by the
        # explicit-detach rule (DuplicateNodeError remains reserved for
        # identity-set validation via ensure_distinct).
        root = _node("Root", 1.0)
        child = _node("Child", 1.0)
        root.add_child(child)
        grand = _node("Grand", 1.0)
        child.add_child(grand)
        with pytest.raises(CyclicHierarchyError, match="already has a parent"):
            root.add_child(grand)


class TestMassAggregation:
    def test_total_system_mass_sums_subtree(self):
        root = _node("Sun", 1.989e30)
        earth = _node("Earth", 5.972e24)
        moon = _node("Moon", 7.342e22)
        root.add_child(earth)
        earth.add_child(moon)
        assert root.total_system_mass_kg() == pytest.approx(
            1.989e30 + 5.972e24 + 7.342e22, rel=1e-12
        )

    def test_partial_mass_never_returned(self):
        # Unknown child mass -> explicit failure, not a partial sum.
        root = _node("Sun", 1.989e30)
        unknown = _node("PlanetIX")  # no properties attached
        root.add_child(unknown)
        with pytest.raises(IncompletePhysicalDataError, match="PlanetIX"):
            root.total_system_mass_kg()

    def test_unknown_attached_block(self):
        root = _node("Sun", 1.989e30)
        child = _node("Child", 1.0e20)
        root.add_child(child)
        child.attach_properties(create_properties(DataProvenance.SIMULATED_DATA))
        with pytest.raises(IncompletePhysicalDataError):
            root.total_system_mass_kg()

    def test_aggregation_deterministic(self):
        root = _node("Root", 7.0)
        for i in range(10):
            root.add_child(_node(f"n{i}", float(i + 1)))
        first = root.total_system_mass_kg()
        for _ in range(200):
            assert root.total_system_mass_kg() == first


class TestNodeValidation:
    def test_identity_type_enforced(self):
        with pytest.raises(TypeError):
            HierarchyNode("Sun")
        with pytest.raises(TypeError):
            HierarchyNode(create_identity("Sun")).add_child("child")

    def test_attach_wrong_block_type(self):
        node = _node("A", 1.0)
        with pytest.raises(TypeError):
            node.attach_properties({"mass_kg": 1.0})
