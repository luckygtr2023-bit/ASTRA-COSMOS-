# Godot Version — ASTRA COSMOS Visualization

- **Engine:** Godot 4.4.1 stable (official)
- **Renderer:** Forward+ (Vulkan primary, DX12 via Vulkan, Metal via MoltenVK on macOS)
- **Fallback:** Compatibility (OpenGL) for web/debug; Forward+ capability detected at launch
- **GDScript:** 2.0 (Godot 4.x)
- **GDExtension:** API v4.4 (C++ with SCons, clang/gcc, MSVC)
- **GLSL:** Vulkan GLSL 450 + Godot Shader Language (`.gdshader`)
- **Compute:** RenderingDevice + GLSL compute (Vulkan only, guarded)

## Compatibility

| Platform | Renderer | Status |
|---|---|---|
| Windows 10/11 (Vulkan) | Forward+ | Tested (RTX 3060, RTX 4070) |
| Linux (Vulkan) | Forward+ | Tested (Ubuntu 22.04) |
| macOS (Metal via MoltenVK) | Forward+ | Expected (un-tested on this CI) |
| Web (WASM) | Compatibility | Preview only, no compute |

## Forward+ Configuration

- `renderer/rendering_method = forward_plus` (desktop), `gl_compatibility` (web)
- Clustered forward lighting: 4096 omni + 4096 spot per view
- MSAA 4x (QUALITY_HIGH+), FXAA low
- Volumetric fog: enabled for nebula/atmosphere, disabled on LOW
- Shadow atlas: 4096 (ULTRA), 2048 (HIGH), 1024 (MEDIUM), disabled on LOW

## Known Limitations

- Web build cannot use `RenderingDevice` compute or volumetric fog
- Forward+ requires Vulkan 1.2; old integrated GPUs fall back to Compatibility (visual parity but no volumetrics)
- GDExtension prebuilt for x86_64 Linux/Windows; ARM requires local SCons build

## Verification

- `godot --version` → 4.4.1.stable.official
- Project opens without shader errors (see `tools/validate_shaders.py`)
- `project.godot` parse OK, `phase_01_foundation` autoloads load
