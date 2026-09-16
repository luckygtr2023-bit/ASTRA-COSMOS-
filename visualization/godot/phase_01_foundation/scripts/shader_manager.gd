# Shader Manager — binds per-classification shader variants (no state mutation)
class_name ShaderManager
extends Node
var _cache: Dictionary = {}
func get_shader(kind: String, classification: String) -> ShaderMaterial:
    var key = kind + ":" + classification
    if _cache.has(key): return _cache[key]
    var path = "res://shaders/%s/%s.gdshader" % [kind.to_lower(), classification.to_lower()]
    # Fallback to generic if speculative not present; but speculative must be distinct (visual honesty)
    var shader_path = path if ResourceLoader.exists(path) else "res://shaders/celestial/star_corona.gdshader"
    var mat = ShaderMaterial.new()
    mat.shader = load(shader_path)
    _cache[key] = mat
    return mat
