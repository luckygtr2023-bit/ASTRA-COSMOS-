
#pragma once
#include <cstdint>
namespace astra::materials8k {
enum class Tier { LOW,MEDIUM,HIGH,ULTRA,CINEMATIC };
struct KTXConfig { bool ktx2=true; bool basis=true; uint32_t max_res=512; uint32_t tile=256*1024; };
KTXConfig config_for_tier(Tier t);
uint32_t streaming_budget(uint32_t vram);
bool needs_8k(Tier t);
}
