# Object Registry — instancing and LOD (no per-object scripts for massive populations)
class_name ObjectRegistry
extends Node

var _multimeshes: Dictionary = {} # kind -> MultiMeshInstance3D
var _pool_size: int = 10000

func register_kind(kind: String, mesh: Mesh, material: Material):
    var mm = MultiMeshInstance3D.new()
    var multimesh = MultiMesh.new()
    multimesh.transform_format = MultiMesh.TRANSFORM_3D
    multimesh.instance_count = 0
    multimesh.visible_instance_count = 0
    multimesh.mesh = mesh
    mm.multimesh = multimesh
    mm.material_override = material
    add_child(mm)
    _multimeshes[kind] = mm

func update_render_state(state: Dictionary):
    # state.objects = [{id, kind, position, lod, classification}]
    var buckets: Dictionary = {}
    for obj in state.get("objects", []):
        var kind = obj.get("kind", "STAR")
        if not buckets.has(kind): buckets[kind] = []
        buckets[kind].append(obj)
    for kind in buckets:
        if not _multimeshes.has(kind): continue
        var arr: Array = buckets[kind]
        var mm: MultiMeshInstance3D = _multimeshes[kind]
        var count = min(arr.size(), _pool_size)
        mm.multimesh.instance_count = count
        mm.multimesh.visible_instance_count = count
        for i in count:
            var obj = arr[i]
            var pos = Vector3(obj["position"][0], obj["position"][1], obj["position"][2])
            # Apply floating origin (AstraBridge singleton)
            pos -= AstraBridge.get_origin_offset()
            var t = Transform3D(Basis.IDENTITY, pos)
            # LOD scale via shader uniform (per-instance custom data)
            mm.multimesh.set_instance_transform(i, t)
            mm.multimesh.set_instance_custom_data(i, Color(float(obj.get("lod",0))/4.0, 0,0,1))
