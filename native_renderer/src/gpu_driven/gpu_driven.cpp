#include "gpu_driven.h"
namespace astra::gpu_driven {
GPUCullStats dispatch_culling(uint32_t total){ GPUCullStats s; s.visible = total*0.7; s.culled_frustum = total*0.2; s.culled_occlusion = total*0.05; s.culled_horizon = total*0.05; return s; }
bool supports_mesh_shader(){ return false; }
bool supports_indirect(){ return true; }
}
