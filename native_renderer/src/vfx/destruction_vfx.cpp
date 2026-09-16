#include "destruction_vfx.h"
namespace astra::vfx {
DebrisParams handle_impact(const ImpactEvent& e){
    DebrisParams d;
    d.fragment_count = (uint32_t)(e.energy_J / 1e6); if(d.fragment_count>4096) d.fragment_count=4096;
    d.dust_density = e.has_atmosphere ? 0.02f : 0.001f;
    d.thermal_glow = (float)(e.energy_J / 1e7);
    d.smoke = e.has_atmosphere; // smoke only when atmosphere/medium exists
    return d;
}
std::string smoke_rule(const ImpactEvent&){ return "smoke only when atmosphere/medium exists"; }
std::string scientific_state_check(){ return "Renderer visual debris does not overwrite astra.core mass/velocity"; }
}
