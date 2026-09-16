
#include "ray_traced.h"
namespace astra::rt {
RTConfig detect_rt_config(uint32_t vram, bool has_rt){
 RTConfig c; c.enabled = has_rt && vram>=8000; c.quality = vram>=12000?Quality::ULTRA: vram>=8000?Quality::HIGH: Quality::LOW;
 c.fallback_raster = !c.enabled; c.denoise = c.enabled; return c;
}
bool supports_acceleration_structure(){ return false; } // true when VK_KHR_acceleration_structure available
std::string fallback_path(const RTConfig& c){ return c.enabled? "hybrid raster+RT":"raster fallback Forward+ 4096 lights"; }
}
