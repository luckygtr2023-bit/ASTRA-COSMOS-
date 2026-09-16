
#pragma once
#include <cstdint>
namespace astra::mesh_shader {
struct Meshlet { uint32_t vertex_count=64, triangle_count=124; float error=0.01f; };
struct VirtualConfig { bool enabled=false; uint32_t max_meshlets=1000000; float screen_error=1.0f; };
VirtualConfig detect_config(uint32_t vram, bool has_mesh_shader);
bool supports_mesh_shader();
uint32_t streaming_budget(uint32_t vram);
}
