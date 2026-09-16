
#include "virtual_geo.h"
namespace astra::mesh_shader {
VirtualConfig detect_config(uint32_t vram, bool has_ms){ VirtualConfig c; c.enabled = has_ms && vram>=6000; c.max_meshlets = vram*100; c.screen_error = c.enabled?0.5f:1.0f; return c; }
bool supports_mesh_shader(){ return false; }
uint32_t streaming_budget(uint32_t vram){ return vram<4000? 2*1024*1024 : 4*1024*1024; }
}
