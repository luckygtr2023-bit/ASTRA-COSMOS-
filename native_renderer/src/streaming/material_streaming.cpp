#include "material_streaming.h"
namespace astra::streaming {
float material_priority(const MaterialRequest& r){
    if(!r.visible) return 0;
    float p = r.screen_size * r.importance;
    if(r.focused) p*=2.f;
    p /= (r.distance+1.f);
    return p;
}
uint32_t mip_for_distance(float d, uint32_t max_mip){
    if(d<10.f) return 0;
    if(d<100.f) return 1;
    if(d<1000.f) return 2;
    return max_mip;
}
std::string fallback_texture(){ return "fallback 1x1 magenta"; }
}
