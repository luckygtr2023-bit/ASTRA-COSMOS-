#include "astrophysical_vfx.h"
namespace astra::vfx {
std::string flare_emissive(const SolarFlareParams& p){ (void)p; return "blackbody 1e7K -> emissive 5.0"; }
std::string cme_visual(const CMEParams& p){ (void)p; return "density->opacity 0.8 velocity->streak"; }
std::string aurora_visual(const AuroraParams& p){ (void)p; return "B field -> curtain 557.7nm"; }
std::string jet_visual(const JetParamsExt& p){ (void)p; return "velocity_c 0.9 -> Doppler g 2.3"; }
bool is_param_driven(const std::string& e){ return e=="solar_flare"||e=="cme"||e=="jet"||e=="aurora"; }
}
