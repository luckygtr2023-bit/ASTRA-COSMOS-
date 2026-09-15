"""Scene graph for hierarchical object management."""

from __future__ import annotations

import math
from typing import Callable, Dict, List, Optional, Tuple

from .render_state import RenderObject, RenderObjectType, RenderState


class SceneNode:
    def __init__(self, render_object, parent=None):
        self.render_object = render_object
        self.parent = parent
        self.children = []
        if parent:
            parent.add_child(self)

    @property
    def object_id(self):
        return self.render_object.object_id

    @property
    def world_position(self):
        if self.parent is None:
            return self.render_object.position
        pp = self.parent.world_position
        lp = self.render_object.position
        return (pp[0] + lp[0], pp[1] + lp[1], pp[2] + lp[2])

    def add_child(self, child):
        if child not in self.children:
            self.children.append(child)
            child.parent = self
            child.render_object.parent_id = self.object_id

    def remove_child(self, child):
        if child in self.children:
            self.children.remove(child)
            child.parent = None
            child.render_object.parent_id = None

    def traverse(self, callback):
        callback(self)
        for child in self.children:
            child.traverse(callback)

    def find_by_id(self, object_id):
        if self.object_id == object_id:
            return self
        for child in self.children:
            result = child.find_by_id(object_id)
            if result:
                return result
        return None

    def get_all_descendants(self):
        result = []
        for child in self.children:
            result.append(child)
            result.extend(child.get_all_descendants())
        return result

    def set_visible_recursive(self, visible):
        self.render_object.visible = visible
        for child in self.children:
            child.set_visible_recursive(visible)


class SceneGraph:
    def __init__(self):
        self._nodes = {}
        self._roots = []

    @property
    def node_count(self):
        return len(self._nodes)

    def add_root(self, render_object):
        node = SceneNode(render_object)
        self._nodes[render_object.object_id] = node
        self._roots.append(node)
        return node

    def add_child(self, parent_id, render_object):
        parent = self._nodes.get(parent_id)
        if parent is None:
            return None
        node = SceneNode(render_object, parent=parent)
        self._nodes[render_object.object_id] = node
        return node

    def remove(self, object_id):
        node = self._nodes.get(object_id)
        if node is None:
            return False
        for child in node.children:
            self.remove(child.object_id)
        if node.parent:
            node.parent.remove_child(node)
        else:
            if node in self._roots:
                self._roots.remove(node)
        del self._nodes[object_id]
        return True

    def get_node(self, object_id):
        return self._nodes.get(object_id)

    def get_roots(self):
        return list(self._roots)

    def traverse(self, callback):
        for root in self._roots:
            root.traverse(callback)

    def get_visible_objects(self):
        return [n.render_object for n in self._nodes.values() if n.render_object.visible]

    def find_by_type(self, obj_type):
        return [n for n in self._nodes.values() if n.render_object.object_type == obj_type]

    def sync_from_render_state(self, render_state):
        current_ids = set(self._nodes.keys())
        state_ids = set(render_state.objects.keys())
        for oid in state_ids - current_ids:
            obj = render_state.objects[oid]
            self.add_root(obj)
        for oid in current_ids - state_ids:
            self.remove(oid)
        for oid in state_ids & current_ids:
            node = self._nodes[oid]
            obj = render_state.objects[oid]
            node.render_object.position = obj.position
            node.render_object.rotation = obj.rotation
            node.render_object.scale = obj.scale
            node.render_object.visible = obj.visible
            node.render_object.lod_level = obj.lod_level

    def clear(self):
        self._nodes.clear()
        self._roots.clear()
