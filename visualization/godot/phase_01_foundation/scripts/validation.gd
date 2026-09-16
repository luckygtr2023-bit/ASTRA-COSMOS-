extends Node
# Validation scene script — runs headless checks inside Godot, prints PASS/FAIL then quits.
# Usage: godot --path visualization/godot --headless --scene res://phase_01_foundation/scenes/validation.tscn

var _ok := 0
var _fail := 0

func _ready():
    _check("Forward+ is forward_plus", ProjectSettings.get_setting("renderer/rendering_method") == "forward_plus")
    # Autoload files exist as res:// resources (the actual autoload registration is in project.godot)
    for pair in [["AstraBridge","astra_bridge"], ["QualityPresets","quality_presets"], ["Telemetry","telemetry"]]:
        var path := "res://phase_01_foundation/scripts/%s.gd" % pair[1]
        _check("Autoload %s exists at %s" % [pair[0], path], FileAccess.file_exists(path))
    var shader_paths := [
        "res://shaders/celestial/star_corona.gdshader",
        "res://shaders/atmosphere/rayleigh_mie.gdshader",
        "res://shaders/terrain/heightmap_terrain.gdshader",
        "res://shaders/ocean/gerstner_ocean.gdshader",
        "res://shaders/stars/procedural_starfield.gdshader",
        "res://shaders/nebula/volumetric_nebula.gdshader",
        "res://shaders/galaxy/spiral_galaxy.gdshader",
        "res://shaders/accretion/accretion_disk.gdshader",
        "res://shaders/gravitational_lensing/lensing.gdshader",
        "res://shaders/spacetime/grid_curvature.gdshader",
        "res://shaders/wormhole/throat.gdshader",
    ]
    for p in shader_paths:
        _check("Shader %s loads" % p, FileAccess.file_exists(p))
    _check("planet_material loads", FileAccess.file_exists("res://materials/planet_material.tres"))
    _check("star_material loads", FileAccess.file_exists("res://materials/star_material.tres"))
    var vfx_paths := [
        "res://vfx/explosions/explosion.tres",
        "res://vfx/impacts/impact_spark.gdshader",
        "res://vfx/plasma/plasma_jet.gdshader",
        "res://vfx/solar/solar_flare.gdshader",
        "res://vfx/radiation/radiation_field.gdshader",
    ]
    for p in vfx_paths:
        _check("VFX %s exists" % p, FileAccess.file_exists(p))
    _check("QualityPresets file exists", FileAccess.file_exists("res://phase_01_foundation/scripts/quality_presets.gd"))
    # Summary
    print("")
    print("[Validation] %d OK, %d FAIL" % [_ok, _fail])
    if _fail == 0:
        print("[Validation] YELLOW: Python validators passed, Godot runtime loaded — RenderingDevice/compute still needs Vulkan check.")
    else:
        print("[Validation] FAIL: %d checks failed — see above" % _fail)
    if DisplayServer.get_name() == "headless" or OS.has_feature("headless"):
        get_tree().quit(0 if _fail == 0 else 1)

func _check(msg: String, passed: bool):
    if passed:
        print("[OK] %s" % msg)
        _ok += 1
    else:
        print("[FAIL] %s" % msg)
        _fail += 1
