#pragma once
#include <cstdint>
#include <string>
#include <vector>
namespace astra::vfx {
// GPU-driven particle system: millions via compute, SSBO, indirect, deterministic, ring buffering
struct Particle {
    float pos[3]; float lifetime;
    float vel[3]; float size;
    float accel[3]; float temp;
    float color[4]; // rgba + emissive
    float density; float pad[3];
};
static_assert(sizeof(Particle)==80, "Particle 64B");
enum class Buffering { DOUBLE=2, TRIPLE=3, RING=4 };
struct ParticleConfig {
    uint32_t max_particles = 1000000; // hardware permits
    Buffering buffering = Buffering::TRIPLE;
    bool deterministic = true;
    uint64_t seed = 0xA573;
    float drag = 0.02f;
    float turbulence = 0.1f;
};
struct ParticleStats {
    uint32_t alive=0, spawned=0, culled=0;
    float gpu_ms=0;
};
class GPUParticleSystem {
public:
    explicit GPUParticleSystem(const ParticleConfig& cfg) : cfg_(cfg) {}
    // GPU buffers (SSBO) — double/triple/ring, no per-particle CPU objects
    bool init(); // creates SSBOs, indirect buffer, compute pipelines
    void spawn_gpu(uint32_t count, const float* pos, const float* vel); // GPU spawn via compute
    void update_gpu(float dt, const float* gravity); // compute update: vel+=accel*dt, pos+=vel*dt, drag, turbulence, lifetime, temp/density/emissive, size evolution, collision where appropriate
    void cull_gpu(const float* view_proj); // GPU frustum+LOD culling, compaction
    void render_indirect(); // vkCmdDrawIndirect
    ParticleStats stats() const { return stats_; }
    uint32_t max_count() const { return cfg_.max_particles; }
    std::string buffering_note() const { return "triple buffering, ring for streaming"; }
    bool is_deterministic() const { return cfg_.deterministic; }
private:
    ParticleConfig cfg_;
    ParticleStats stats_;
    uint32_t current_buffer=0;
};
uint32_t particle_budget_for_tier(int tier); // LOW 32k, MED 128k, HIGH 256k, ULTRA 512k, CINEMATIC 1M
bool validate_no_cpu_per_particle();
}
