# ASTRA Native Renderer — Maximum-Fidelity C++20 / Vulkan 1.3

**Branch:** `arena/01a0a5a2-astra-cosmos` (NO-GODOT)
**Target:** AAA-level space simulation visuals at `1e26` scale, scientific authority preserved
**Toolchain:** C++20 GCC 12.2, CMake 4.4.3, Ninja 1.13, Vulkan 1.3, GLSL→SPIR-V, GLFW/SDL3, EnTT, Dear ImGui, Tracy, RenderDoc

## Architecture

```
ASTRA Scientific Engine (Python astra.core.Engine, double, deterministic)
        ↓ snapshot Tick 42 sim_time 1234.5
Visualization API / RenderState (JSON bridge_state.json 30 Hz → binary ring-buffer future)
        ↓ hash != last_hash
Native C++ Renderer (Vulkan FrameGraph, double→float relative, floating-origin)
        ↓ vkCmdDrawIndirect / compute dispatch 256 threads
GPU (Vulkan 1.3, Forward+ clustered 4096 lights, HDR 16F, TAA, volumetrics 192)
        ↓ swapchain 1920×1080 60Hz
Display + Dear ImGui debug overlay
```

**Renderer never modifies scientific truth.** Consumes `object states, coordinates, velocities, masses, trajectories, spacetime geometry, observer, sim_time, physical, destruction, astronomical`.

## Folder Map (mirrors spec §15)

```
renderer/            → native_renderer/src/rhi + gpu
rhi/                 → Vulkan abstraction (VkDevice, FrameGraph)
gpu/                 → buffers, descriptors, bindless
shaders/             → GLSL 460 → SPIR-V (common, terrain, atmosphere, ocean, stars, galaxy, black_hole, lensing, relativity, wormhole, vfx, lighting, postprocess, compute, culling)
materials/           → PBR (clear-coat, sheen, HDR)
textures/            → KTX2/basis, ppm LUTs
meshes/              → EnTT + meshoptimizer LOD
terrain/             → procedural displacement height_scale 400, virtual texturing
atmosphere/          → Rayleigh 4e-6 Mie 2.1e-5 O'Neil + volumetrics
volumetrics/         → fog 0.004 albedo, clouds 2.5D raymarch, nebula FogVolume
particles/           → compute 1M GPU particles RANDOM_SEED
astronomy/           → stellar (star_corona), planetary, galactic (spiral b=0.22)
relativity/          → Doppler g^3, beaming, aberration spectral
black_hole/          → shadow 2.6r_s photon 1.5r_s, accretion T∝r-3/4, ray-march 256
spacetime/           → grid_curvature height displacement
vfx/                 → impact_spark, plasma_jet, solar_flare, well_rings, debris
camera/              → orbital/free/spacecraft/observation/cinematic/replay, dolly, TAA
lighting/            → PBR + HDR + exposure + ACES/AgX tonemap, 4096 lights clustered
postprocess/         → bloom 0.8, DoF, motion blur, color management
streaming/           → async 4MB/frame 256KB tile, virtualized
lod/culling/         → HLOD 32 clusters, frustum+occlusion, GPU culling indirect
debug/profiling/     → ImGui + Tracy + RenderDoc + validation layers
tools/               → validate_native_project.py 60 checks
tests/               → gtest coordinate/floating-origin/LOD/culling
```

## Build (without GPU — static)

```bash
pip install --break-system-packages cmake ninja  # 4.4.3/1.13 verified
git clone --depth 1 https://github.com/KhronosGroup/Vulkan-Headers /home/user/Vulkan-Headers
git clone --depth 1 https://github.com/skypjack/entt /home/user/entt
git clone --depth 1 https://github.com/ocornut/imgui /home/user/imgui
git clone --depth 1 https://github.com/glfw/glfw /home/user/glfw
cmake -S native_renderer -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build -j2
./build/astra_native --help
python native_renderer/tools/validate_native_project.py  # 60 OK static
pytest tests/test_native_renderer.py -q
```

With Vulkan SDK (`apt install libvulkan-dev` when network unblocked):
```bash
cmake -S native_renderer -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DASTRA_ENABLE_VALIDATION=ON
cmake --build build -j4 && ./build/astra_native --headless --benchmark  # requires GPU
glslangValidator -V native_renderer/shaders/**/*.glsl  # SPIR-V
renderdoc capture ./build/astra_native --scene benchmark
```

## Godot Comparison

See `ASTRA_MAXIMUM_RENDERER_REPORT.md` §10. With Godot 6.8/10 (fast), without (this) 8.7/10 ceiling (AAA). This renderer is `POSSIBLE WITH CONDITIONS` for AAA — target is HDR+PBR+volumetrics+TAA+60fps, not marketing.

## Scientific Authority

`Bridge::poll("bridge_state.json")` 30Hz hash, `FloatingOrigin::world_to_relative = world - camera_origin` double→float, `WorldHierarchy 5 levels` DAG, no `teleport`, `SPECULATIVE` wormhole distinct shader + label, `Telemetry` `draw_calls 60fps`.

## Status

*Implementable*: all files authored. *Statically validatable*: Python+glslang static. *Compiled*: needs `cmake/ninja/vulkan`. *Runtime/GPU verified*: needs local `Vulkan` + `RTX` host — marked `NOT VERIFIED` in CI.
