"""VFX system manager."""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

from .vfx_effect import VFXEffect, VFXType


class VFXSystem:
    def __init__(self, max_effects=256):
        self.max_effects = max_effects
        self._effects = {}
        self._effect_groups = {}
        self._update_hooks = []
        self._completion_callbacks = {}

    @property
    def active_count(self):
        return sum(1 for e in self._effects.values() if e.is_active)

    @property
    def total_count(self):
        return len(self._effects)

    def add_effect(self, effect):
        if len(self._effects) >= self.max_effects:
            raise RuntimeError(f"Maximum VFX count ({self.max_effects}) reached.")
        self._effects[effect.effect_id] = effect

    def remove_effect(self, effect_id):
        if effect_id in self._effects:
            del self._effects[effect_id]
            for group_effects in self._effect_groups.values():
                if effect_id in group_effects:
                    group_effects.remove(effect_id)
            self._completion_callbacks.pop(effect_id, None)
            return True
        return False

    def get_effect(self, effect_id):
        return self._effects.get(effect_id)

    def get_effects_by_type(self, vfx_type):
        return [e for e in self._effects.values() if e.vfx_type == vfx_type]

    def add_update_hook(self, hook):
        self._update_hooks.append(hook)

    def set_completion_callback(self, effect_id, callback):
        self._completion_callbacks[effect_id] = callback

    def create_group(self, group_name):
        if group_name not in self._effect_groups:
            self._effect_groups[group_name] = []

    def add_to_group(self, group_name, effect_id):
        if group_name not in self._effect_groups:
            self.create_group(group_name)
        self._effect_groups[group_name].append(effect_id)

    def get_group(self, group_name):
        ids = self._effect_groups.get(group_name, [])
        return [self._effects[eid] for eid in ids if eid in self._effects]

    def update(self, dt):
        completed = 0
        for effect in list(self._effects.values()):
            if not effect.is_active:
                continue
            effect.update(dt)
            for hook in self._update_hooks:
                hook(effect, dt)
            if not effect.is_active:
                completed += 1
                callback = self._completion_callbacks.get(effect.effect_id)
                if callback:
                    callback(effect)
        return completed

    def cleanup(self):
        to_remove = [eid for eid, e in self._effects.items() if not e.is_active]
        for eid in to_remove:
            del self._effects[eid]
        return len(to_remove)

    def clear(self):
        self._effects.clear()
        self._effect_groups.clear()
        self._completion_callbacks.clear()

    def get_all_states(self):
        return {eid: e.get_state() for eid, e in self._effects.items() if e.is_active}

    def serialize(self):
        return {"effects": {eid: e.to_dict() for eid, e in self._effects.items()}, "groups": dict(self._effect_groups)}
