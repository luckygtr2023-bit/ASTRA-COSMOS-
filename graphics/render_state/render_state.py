"""Render state and render object definitions."""

from __future__ import annotations

from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple


class RenderObjectType(Enum):
    PLANET = auto()
    MOON = auto()
    STAR = auto()
    BLACK_HOLE = auto()
    ACCRETION_DISK = auto()
    ASTEROID = auto()
    COMET = auto()
    NEBULA = auto()
    WORMHOLE = auto()
    WARP_FIELD = auto()
    SPACECRAFT = auto()
    DEBRIS = auto()
    ATMOSPHERE = auto()
    PARTICLE_EFFECT = auto()
    BACKGROUND = auto()
    CUSTOM = auto()


class RenderObject:
    def __init__(self, object_id, object_type, position=(0.0, 0.0, 0.0), rotation=(0.0, 0.0, 0.0, 1.0), scale=(1.0, 1.0, 1.0)):
        self.object_id = object_id
        self.object_type = object_type
        self.position = position
        self.rotation = rotation
        self.scale = scale
        self.visible = True
        self.lod_level = 0
        self.material_name = None
        self.shader_name = None
        self.mesh_name = None
        self.custom_data = {}
        self.parent_id = None
        self.children_ids = []
        self.world_matrix = None
        self.bounding_radius = 1.0
        self.sort_priority = 0

    def set_uniform_scale(self, s):
        self.scale = (s, s, s)

    def get_custom(self, key, default=None):
        return self.custom_data.get(key, default)

    def set_custom(self, key, value):
        self.custom_data[key] = value

    def to_dict(self):
        return {"object_id": self.object_id, "type": self.object_type.name, "position": list(self.position), "rotation": list(self.rotation), "scale": list(self.scale), "visible": self.visible, "lod_level": self.lod_level, "material_name": self.material_name, "shader_name": self.shader_name, "bounding_radius": self.bounding_radius}


class RenderState:
    def __init__(self):
        self.frame_number = 0
        self.time = 0.0
        self.delta_time = 0.0
        self.camera_position = (0.0, 0.0, 10.0)
        self.camera_target = (0.0, 0.0, 0.0)
        self.camera_up = (0.0, 1.0, 0.0)
        self.camera_fov = 60.0
        self.camera_near = 0.01
        self.camera_far = 1e10
        self.view_matrix = None
        self.projection_matrix = None
        self.ambient_light = (0.05, 0.05, 0.1)
        self.lights = []
        self.objects = {}
        self.particle_draw_calls = []
        self.vfx_states = {}
        self.background_color = (0.0, 0.0, 0.02)
        self.starfield_enabled = True
        self.post_processing_enabled = True

    def add_object(self, obj):
        self.objects[obj.object_id] = obj

    def remove_object(self, object_id):
        if object_id in self.objects:
            del self.objects[object_id]
            return True
        return False

    def get_object(self, object_id):
        return self.objects.get(object_id)

    def get_objects_by_type(self, obj_type):
        return [o for o in self.objects.values() if o.object_type == obj_type]

    def get_visible_objects(self):
        return [o for o in self.objects.values() if o.visible]

    def add_light(self, light_id, position, color=(1.0, 1.0, 1.0), intensity=1.0, light_type="directional"):
        self.lights.append({"light_id": light_id, "position": position, "color": color, "intensity": intensity, "type": light_type})

    def set_vfx_state(self, vfx_id, state):
        self.vfx_states[vfx_id] = state

    def get_vfx_state(self, vfx_id):
        return self.vfx_states.get(vfx_id)

    def clear(self):
        self.objects.clear()
        self.particle_draw_calls.clear()
        self.vfx_states.clear()
        self.lights.clear()

    def to_dict(self):
        return {"frame": self.frame_number, "time": self.time, "camera": {"position": list(self.camera_position), "target": list(self.camera_target), "fov": self.camera_fov}, "objects": {oid: o.to_dict() for oid, o in self.objects.items()}, "lights": list(self.lights), "vfx_states": dict(self.vfx_states), "particle_count": len(self.particle_draw_calls)}
