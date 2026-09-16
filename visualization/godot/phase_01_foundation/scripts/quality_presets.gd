# Quality Presets — detects hardware, controls feature set (autoload)
extends Node

enum Preset { LOW, MEDIUM, HIGH, ULTRA, CINEMATIC }

var current: Preset = Preset.HIGH
var _vram_mb: int = 4096

func _ready():
    _detect_hardware()
    apply(current)

func _detect_hardware():
    var adapter = RenderingServer.get_video_adapter_name()
    var vram = OS.get_memory_info()["available"] / 1024 / 1024 if OS.has_feature("memory_info") else 4096
    # Heuristic: if adapter contains "Intel" or vram < 2048 -> LOW
    if adapter.contains("Intel") or vram < 3000:
        current = Preset.LOW
    elif adapter.contains("RTX 40") or adapter.contains("RX 7"):
        current = Preset.ULTRA
    print("[QualityPresets] adapter=", adapter, " vram~", vram, " -> ", Preset.keys()[current])

func apply(p: Preset):
    current = p
    var env = get_viewport().world_3d.environment if get_viewport().world_3d else null
    match p:
        Preset.LOW:
            RenderingServer.environment_set_ssao_quality(RenderingServer.ENV_SSAO_QUALITY_LOW, false, 0.5, 2, 50, 300)
            if env: env.volumetric_fog_enabled = false; env.glow_enabled = false
        Preset.MEDIUM:
            if env: env.volumetric_fog_enabled = false; env.glow_enabled = true
        Preset.HIGH:
            if env: env.volumetric_fog_enabled = true; env.glow_enabled = true
        Preset.ULTRA, Preset.CINEMATIC:
            if env: env.volumetric_fog_enabled = true; env.glow_enabled = true; env.glow_intensity = 0.6
    print("[QualityPresets] applied ", Preset.keys()[p])

func is_forward_plus() -> bool:
    return RenderingServer.get_current_rendering_method() == "forward_plus"
