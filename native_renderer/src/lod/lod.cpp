#include <cmath>
// LOD/HLOD — distance tiers 0-5/5-50/50-500/500-5k/5k+ LOD0-4, HLOD 32/cluster dither 0.2s
namespace astra::lod {
enum LOD{ L0=0,L1,L2,L3,L4,CULLED };
inline LOD get_lod(float dist){
    if(dist<5.f) return L0;
    if(dist<50.f) return L1;
    if(dist<500.f) return L2;
    if(dist<5000.f) return L3;
    if(dist<10000.f) return L4;
    return CULLED;
}
constexpr int HLOD_CLUSTER=32;
}
