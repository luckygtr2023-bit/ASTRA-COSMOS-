#include <cstdint>
// VFX — compute particles 1M RANDOM_SEED, impact_spark, plasma_jet, solar_flare, well_rings, debris
namespace astra::vfx {
struct ParticleBudget { uint32_t low=32, med=128, high=256, ultra=512, cinematic=1024; };
constexpr ParticleBudget BUDGET{};
// Note: native can exceed 1024 → 1M for cinematic via indirect dispatch
void emit_burst(uint32_t count, float dt){ (void)count; (void)dt; /* dispatch 64 threads */ }
}
