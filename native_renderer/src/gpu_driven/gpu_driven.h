#pragma once
#include <cstdint>
namespace astra::gpu_driven {
struct IndirectDraw { uint32_t count=0, instance_count=1, first=0, base=0; };
struct GPUCullStats { uint32_t visible=0, culled_frustum=0, culled_occlusion=0, culled_horizon=0; };
GPUCullStats dispatch_culling(uint32_t total);
bool supports_mesh_shader();
bool supports_indirect();
}
