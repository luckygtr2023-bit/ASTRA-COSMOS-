
#pragma once
#include <string>
namespace astra::rt {
enum class Quality { OFF, LOW, MEDIUM, HIGH, ULTRA };
struct RTConfig { bool enabled=false; Quality quality=Quality::OFF; bool fallback_raster=true; bool denoise=true; };
RTConfig detect_rt_config(uint32_t vram_mb, bool has_ray_tracing);
bool supports_acceleration_structure();
std::string fallback_path(const RTConfig& c);
}
