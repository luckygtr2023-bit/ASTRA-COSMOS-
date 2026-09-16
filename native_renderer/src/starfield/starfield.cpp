#include "starfield.h"
namespace astra::starfield {
StarLOD lod_for_distance(double dist, double rad){
    if(dist > 1e12) return StarLOD::POINT;
    if(dist > 1e10) return StarLOD::BILLBOARD;
    if(dist > 1e9) return StarLOD::IMPOSTOR;
    return StarLOD::PROCEDURAL_SURFACE;
}
uint32_t streaming_budget(uint32_t vram){ return vram<4000? 5*1024*1024 : 50*1024*1024; }
}
