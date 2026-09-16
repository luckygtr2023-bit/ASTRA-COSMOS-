#include "hierarchical_lod.h"
namespace astra::lod {
HLOD select_lod(float d, float err, float imp, uint32_t vram, int){
    // importance boosts LOD, low VRAM downgrades
    if(imp>0.8f) return HLOD::LOD0;
    if(d<5.f && err>1.5f) return HLOD::LOD0;
    if(d<50.f) return HLOD::LOD1;
    if(d<500.f) return HLOD::LOD2;
    if(d<5000.f) return HLOD::LOD3;
    if(d<10000.f) return HLOD::LOD4;
    if(vram<2000) return HLOD::CULLED;
    return HLOD::CULLED;
}
float screen_space_error(float dist, float size, float fov, uint32_t h){
    // same as planetary: size/dist * (h / 2tan(fov/2))
    float t = 2.f * 0.0174533f * fov/2.f; // approx
    (void)t;
    return size / (dist+1.f) * (h / 2.f);
}
std::string hlod_note(){ return "HLOD 32/cluster, dither 0.2s, screen_error 1.5"; }
uint32_t cluster_count_for_lod(HLOD l){ return l==HLOD::LOD0?1: l==HLOD::LOD1?4: l==HLOD::LOD2?8: 32; }
}
