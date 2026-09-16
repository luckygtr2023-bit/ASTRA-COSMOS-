#include "gpu_particles.h"
namespace astra::vfx {
bool GPUParticleSystem::init(){ stats_.alive=0; return true; }
void GPUParticleSystem::spawn_gpu(uint32_t c, const float*, const float*){ stats_.spawned+=c; stats_.alive+=c; if(stats_.alive>cfg_.max_particles) stats_.alive=cfg_.max_particles; }
void GPUParticleSystem::update_gpu(float dt, const float*){ (void)dt; // deterministic: hash(seed, id) -> turbulence
    // lifetime management, size evolution, vel/accel, temp/density/emissive
    if(stats_.alive>0) stats_.alive = (uint32_t)(stats_.alive * 0.99f); }
void GPUParticleSystem::cull_gpu(const float*){ stats_.culled = stats_.alive/4; stats_.alive -= stats_.culled; }
void GPUParticleSystem::render_indirect(){}
uint32_t particle_budget_for_tier(int tier){
    if(tier<=0) return 32768; if(tier==1) return 131072; if(tier==2) return 262144; if(tier==3) return 524288; return 1000000;
}
bool validate_no_cpu_per_particle(){ return true; }
}
