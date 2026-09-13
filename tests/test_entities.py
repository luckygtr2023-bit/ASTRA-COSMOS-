"""Test suite for ASTRA Core entities."""

import pytest
from astra.core.entities import EntityManager, Entity, Component, Query
from astra.core.exceptions import EntityError


class TestComponent:
    """Tests for Component class."""

    def test_component_creation(self):
        """Test basic component creation."""
        comp = Component()
        assert comp.id.startswith("component_Component_")

    def test_component_clone(self):
        """Test component cloning."""
        comp = Component()
        clone = comp.clone()
        assert clone.id == comp.id


class TestEntity:
    """Tests for Entity class."""

    def test_entity_creation(self):
        """Test entity creation via manager."""
        manager = EntityManager()
        entity = manager.create_entity("test_entity")
        assert entity.name == "test_entity"
        assert entity.enabled is True

    def test_entity_components(self):
        """Test adding and removing components."""
        manager = EntityManager()
        entity = manager.create_entity()

        comp1 = Component()
        comp2 = Component()

        entity.add_component(comp1)
        entity.add_component(comp2)

        assert len(entity.components) == 2
        assert comp1.id in entity.components
        assert comp2.id in entity.components

        entity.remove_component(comp1.id)
        assert len(entity.components) == 1

    def test_entity_tags(self):
        """Test entity tags."""
        manager = EntityManager()
        entity = manager.create_entity()

        entity.tags.add("tag1")
        entity.tags.add("tag2")

        assert "tag1" in entity.tags
        assert "tag2" in entity.tags

    def test_entity_clone(self):
        """Test entity cloning."""
        manager = EntityManager()
        entity = manager.create_entity("original")
        entity.tags.add("test_tag")

        clone = entity.clone()
        assert clone.name == entity.name
        assert clone.tags == entity.tags
        assert clone.id == entity.id


class TestEntityManager:
    """Tests for EntityManager."""

    def test_create_and_destroy(self):
        """Test entity creation and destruction."""
        manager = EntityManager()
        entity = manager.create_entity("test")
        assert manager.get_entity_count() == 1

        manager.destroy_entity(entity.id.value)
        assert manager.get_entity_count() == 0

    def test_get_entity(self):
        """Test getting entities."""
        manager = EntityManager()
        entity = manager.create_entity("test")

        retrieved = manager.get_entity(entity.id.value)
        assert retrieved is not None
        assert retrieved.name == "test"

        # Get non-existent
        assert manager.get_entity("nonexistent") is None

    def test_get_entity_or_raise(self):
        """Test get_entity_or_raise."""
        manager = EntityManager()
        entity = manager.create_entity("test")

        retrieved = manager.get_entity_or_raise(entity.id.value)
        assert retrieved.name == "test"

        with pytest.raises(EntityError):
            manager.get_entity_or_raise("nonexistent")

    def test_query_entities(self):
        """Test querying entities."""
        manager = EntityManager()

        e1 = manager.create_entity("e1")
        e2 = manager.create_entity("e2")
        e3 = manager.create_entity("e3")

        e1.tags.add("type_a")
        e2.tags.add("type_a")
        e3.tags.add("type_b")

        # Query by tag
        query = Query().with_tag("type_a")
        results = manager.query(query)
        assert len(results) == 2

        # Query all
        all_results = manager.query(Query())
        assert len(all_results) == 3

    def test_query_with_component(self):
        """Test querying by component."""
        manager = EntityManager()

        e1 = manager.create_entity("e1")
        e2 = manager.create_entity("e2")

        comp = Component()
        e1.add_component(comp)

        query = Query().with_component(Component)
        results = manager.query(query)
        assert len(results) == 1
        assert results[0].id == e1.id

    def test_query_enabled_only(self):
        """Test enabled-only query."""
        manager = EntityManager()

        e1 = manager.create_entity("e1")
        e2 = manager.create_entity("e2")
        e2.enabled = False

        query = Query().enabled_only()
        results = manager.query(query)
        assert len(results) == 1
        assert results[0].id == e1.id

    def test_deterministic_iteration(self):
        """Test that iteration is deterministic."""
        manager = EntityManager()

        # Create entities in specific order
        entities = [manager.create_entity(f"e{i}") for i in range(10)]

        # Query multiple times
        results1 = manager.query(Query())
        results2 = manager.query(Query())

        # Should be same order
        ids1 = [e.id.value for e in results1]
        ids2 = [e.id.value for e in results2]
        assert ids1 == ids2

    def test_safe_iteration_during_mutation(self):
        """Test that iteration is safe during mutation."""
        manager = EntityManager()

        for i in range(5):
            manager.create_entity(f"e{i}")

        # Iterate and destroy - should not cause issues
        for entity in manager.query_iterator(Query()):
            manager.destroy_entity(entity.id.value)

        assert manager.get_entity_count() == 0

    def test_clear(self):
        """Test clearing all entities."""
        manager = EntityManager()

        for _ in range(10):
            manager.create_entity()

        manager.clear()
        assert manager.get_entity_count() == 0

    def test_state_snapshot(self):
        """Test state snapshot."""
        manager = EntityManager()
        e1 = manager.create_entity("test")
        e1.tags.add("snapshot_test")

        snapshot = manager.get_state_snapshot()
        assert "entities" in snapshot
        assert len(snapshot["entities"]) == 1

    def test_restore_from_snapshot(self):
        """Test restoring from snapshot."""
        manager = EntityManager()
        e1 = manager.create_entity("test")
        e1.tags.add("restore_test")

        snapshot = manager.get_state_snapshot()

        # Clear and restore
        manager.clear()
        manager.restore_from_snapshot(snapshot)

        assert manager.get_entity_count() == 1
