# Coordinate Bridge — floating-origin helper
class_name CoordinateBridge
extends Node

# Converts world (ASTRA hierarchical) → local (Godot) = world - origin_offset
# Preserves double-precision by keeping origin near camera.

var origin_offset: Vector3 = Vector3.ZERO

func world_to_local(world_pos: Vector3) -> Vector3:
    return world_pos - origin_offset

func local_to_world(local_pos: Vector3) -> Vector3:
    return local_pos + origin_offset

func rebase(new_origin: Vector3):
    # Called when ASTRA OriginRebaser emits; tween for smoothness, no teleport
    var tween = get_tree().create_tween()
    tween.tween_property(self, "origin_offset", new_origin, 0.6).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
    print("[CoordinateBridge] rebasing ", origin_offset, " -> ", new_origin)
