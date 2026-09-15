"""Performance optimization for graphics: LOD, culling, batching, instancing."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple


class GraphicsLOD:
    """Level-of-detail selector for graphics objects."""

    def __init__(self, distances=None):
        self.distances = distances or [10, 100, 1000, 10000]
        self._levels = ["ULTRA", "HIGH", "MEDIUM", "LOW", "IMPOSTOR"]

    def select(self, distance, bounding_radius=1.0):
        if distance < self.distances[0]:
            return self._levels[0]
        for i, d in enumerate(self.distances[1:], start=1):
            if distance < d:
                return self._levels[i]
        return self._levels[-1]

    def get_level_for_distance(self, distance):
        return self.select(distance)

    @property
    def level_count(self):
        return len(self._levels)


class FrustumCuller:
    """Simple frustum culling (CPU-side, renderer-independent)."""

    def __init__(self, fov=60.0, aspect=16/9, near=0.1, far=1e6):
        self.fov = fov
        self.aspect = aspect
        self.near = near
        self.far = far
        self._camera_pos = (0.0, 0.0, 0.0)
        self._camera_dir = (0.0, 0.0, -1.0)

    def set_camera(self, position, direction=(0.0, 0.0, -1.0)):
        self._camera_pos = position
        self._camera_dir = direction

    def is_visible(self, position, bounding_radius=1.0):
        # Simplified: check distance to camera within near/far and in front
        dx = position[0] - self._camera_pos[0]
        dy = position[1] - self._camera_pos[1]
        dz = position[2] - self._camera_pos[2]
        dist = math.sqrt(dx*dx + dy*dy + dz*dz)
        if dist - bounding_radius > self.far or dist + bounding_radius < self.near:
            return False
        # Check in front of camera (dot product with dir >0)
        dot = dx*self._camera_dir[0] + dy*self._camera_dir[1] + dz*self._camera_dir[2]
        # For simplicity, assume camera looking -Z, so visible if dz < 0 (in front)
        # If direction is -Z, then dot = -dz
        return dot > -bounding_radius

    def cull(self, objects):
        visible = []
        culled = []
        for obj in objects:
            pos = getattr(obj, "position", (0,0,0))
            rad = getattr(obj, "bounding_radius", 1.0)
            if self.is_visible(pos, rad):
                visible.append(obj)
            else:
                culled.append(obj)
        return visible, culled

    def to_dict(self):
        return {"fov": self.fov, "aspect": self.aspect, "near": self.near, "far": self.far}


class DrawBatcher:
    """Batches draw calls by material/shader to minimize state changes."""

    def __init__(self, max_batch_size=1000):
        self.max_batch_size = max_batch_size
        self._batches: Dict[str, List[Any]] = {}

    def add(self, draw_call):
        key = getattr(draw_call, "material_name", None) or getattr(draw_call, "shader_name", None) or "default"
        if isinstance(draw_call, dict):
            key = draw_call.get("material_name") or draw_call.get("shader_name") or draw_call.get("type") or "default"
        if key not in self._batches:
            self._batches[key] = []
        self._batches[key].append(draw_call)

    def get_batches(self):
        result = []
        for key, calls in self._batches.items():
            for i in range(0, len(calls), self.max_batch_size):
                result.append({"key": key, "calls": calls[i:i+self.max_batch_size], "count": min(self.max_batch_size, len(calls)-i)})
        return result

    def clear(self):
        self._batches.clear()

    @property
    def batch_count(self):
        return sum((len(calls) + self.max_batch_size -1)//self.max_batch_size for calls in self._batches.values())

    @property
    def draw_call_count(self):
        return sum(len(calls) for calls in self._batches.values())


class InstanceManager:
    """Manages GPU instancing for repeated meshes."""

    def __init__(self, max_instances=10000):
        self.max_instances = max_instances
        self._instances: Dict[str, List[Tuple[float, float, float]]] = {}

    def add_instance(self, mesh_name, position):
        if mesh_name not in self._instances:
            self._instances[mesh_name] = []
        if len(self._instances[mesh_name]) < self.max_instances:
            self._instances[mesh_name].append(position)
            return True
        return False

    def get_instances(self, mesh_name):
        return list(self._instances.get(mesh_name, []))

    def get_all(self):
        return {k: list(v) for k, v in self._instances.items()}

    def clear(self, mesh_name=None):
        if mesh_name:
            self._instances.pop(mesh_name, None)
        else:
            self._instances.clear()

    @property
    def total_instances(self):
        return sum(len(v) for v in self._instances.values())

    def to_dict(self):
        return {"max_instances": self.max_instances, "meshes": {k: len(v) for k, v in self._instances.items()}}
