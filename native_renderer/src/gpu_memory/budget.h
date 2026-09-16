#pragma once
#include <cstdint>
#include <string>
namespace astra::gpu_memory {
enum class ResourceType { GEOMETRY, TEXTURES, MATERIALS, PARTICLES, VOLUMETRICS, FRAMEBUFFERS, HISTORY, ACCELERATION };
struct Budget {
    uint64_t total_mb=4096;
    uint64_t geometry=512, textures=1024, materials=256, particles=256, volumetrics=256, framebuffers=512, history=128, accel=0;
    uint64_t used() const { return geometry+textures+materials+particles+volumetrics+framebuffers+history+accel; }
    float pressure() const { return float(used())/float(total_mb); }
    bool over_budget() const { return used()>total_mb; }
};
struct EvictionPolicy {
    enum class Strategy { LRU, PRIORITY, SIZE };
    Strategy strategy=Strategy::LRU;
    std::string fallback="graceful degrade, not crash";
};
Budget budget_for_tier(int tier);
bool track_usage(Budget& b, ResourceType t, uint64_t bytes);
bool evict_lru(Budget& b, uint64_t need);
}
