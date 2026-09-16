#pragma once
#include <cstdint>
#include <string>
namespace astra::vfx {
// Destruction pipeline: Impact -> Energy -> Collision -> Fragmentation -> Debris -> GPU VFX
enum class ImpactStage { IMPACT, ENERGY, COLLISION, FRACTURE, FRAGMENTATION, DEBRIS, ATMOSPHERIC, PARTICLES, LIGHT_HEAT, FADE };
struct ImpactEvent { double energy_J=1e9; double velocity=5000; double mass_kg=1000; bool has_atmosphere=false; std::string classification="REAL"; };
struct DebrisParams { uint32_t fragment_count=256; float dust_density=0.02f; float thermal_glow=800.f; bool smoke=false; };
DebrisParams handle_impact(const ImpactEvent& e); // must not invent physics, visualizes simulation result only
std::string smoke_rule(const ImpactEvent& e); // smoke only when atmosphere/medium exists
std::string scientific_state_check(); // returns preserved note
}
