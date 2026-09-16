#include "volumetrics_hardened.h"
namespace astra::vfx {
float ray_march_cost(const VolumeConfig& c){ return c.slices * 0.005f; } // 64->0.32ms
bool is_physically_meaningful(const std::string& m){
    if(m=="nebula"||m=="gas_cloud"||m=="dust"||m=="atmosphere"||m=="stellar_plasma") return true;
    if(m=="smoke"||m=="fire") return false; // only when atmosphere/medium or CINEMATIC
    return false;
}
uint32_t slices_for_tier(int t){ if(t<=0) return 0; if(t==1) return 32; if(t==2) return 64; if(t==3) return 128; return 192; }
}
