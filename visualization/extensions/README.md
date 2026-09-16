# Extensions — C++ GDExtension

## When to Use

- 50k+ instances, 60 Hz buffer prep (GDScript loop 1.2ms → compute 0.08ms)
- NOT for gameplay logic, not for scientific simulation

## Build

```bash
git clone --recursive https://github.com/godotengine/godot-cpp -b 4.4
cd visualization/extensions
scons target=template_release -j4  # produces bin/libastra_visualization.linux.template_release.x86_64.so
```

## Files

- `../scripts/cpp/gdextension_instance.cpp` — AstraInstanceHelper (RefCounted)
- `../scripts/cpp/SConstruct` — SCons

## API

```gdscript
var helper = AstraInstanceHelper.new()
var packed: PackedVector3Array = helper.prepare_buffers(origin_offset, count)
# Or GPU path:
# RenderingDevice.compute_list_begin(); ... ; compute_list_end()
```

## Fallback

If `libastra_visualization` missing or Vulkan unavailable, `ObjectRegistry` uses GDScript loop (tested, 10k <1.2ms).

## Thread Safety

Main thread only. `RenderingDevice` is main-thread.

## Platform

- Linux x86_64, Windows x86_64 prebuilt (CI)
- macOS/arm64 requires local build (MoltenVK)
