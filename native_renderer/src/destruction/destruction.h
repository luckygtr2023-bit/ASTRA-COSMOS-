
#pragma once
#include <string>
namespace astra::destruction {
enum class Stage { IMPACT, ENERGY, COLLISION, FRACTURE, FRAGMENTATION, DEBRIS, ATMOSPHERIC, PARTICLES, LIGHT_HEAT, AUDIO };
struct DestructionConfig { bool rbd_enabled=false; bool fracture=true; uint32_t max_fragments=1024; };
DestructionConfig detect_config(uint32_t vram);
std::string scientific_state_preserved();
}
