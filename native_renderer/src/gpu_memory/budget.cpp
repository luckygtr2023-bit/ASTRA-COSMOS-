#include "budget.h"
namespace astra::gpu_memory {
Budget budget_for_tier(int tier){
    if(tier<=0) return {2048,256,512,128,64,128,256,64,0};
    if(tier==1) return {4096,512,1024,256,128,256,512,128,0};
    if(tier==2) return {8192,1024,2048,512,256,512,1024,256,64};
    return {16384,2048,4096,1024,512,1024,2048,512,128};
}
bool track_usage(Budget& b, ResourceType t, uint64_t bytes){
    uint64_t mb = bytes/(1024*1024);
    switch(t){
        case ResourceType::GEOMETRY: b.geometry+=mb; break;
        case ResourceType::TEXTURES: b.textures+=mb; break;
        case ResourceType::MATERIALS: b.materials+=mb; break;
        case ResourceType::PARTICLES: b.particles+=mb; break;
        case ResourceType::VOLUMETRICS: b.volumetrics+=mb; break;
        case ResourceType::FRAMEBUFFERS: b.framebuffers+=mb; break;
        case ResourceType::HISTORY: b.history+=mb; break;
        case ResourceType::ACCELERATION: b.accel+=mb; break;
    }
    return !b.over_budget();
}
bool evict_lru(Budget& b, uint64_t need){
    uint64_t mb = need/(1024*1024);
    if(b.textures>=mb){ b.textures-=mb; return true; }
    if(b.geometry>=mb){ b.geometry-=mb; return true; }
    return false;
}
}
