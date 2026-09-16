#pragma once
#include <cstdint>
#include <string>
namespace astra::lod {
// Hierarchical LOD LOD0-4 + HLOD clusters, screen-space error, importance, VRAM, observer mode, scientific importance
enum class HLOD { LOD0=0, LOD1, LOD2, LOD3, LOD4, CULLED };
struct LODConfig {
    float distance_thresholds[5]={5.f,50.f,500.f,5000.f,10000.f};
    float screen_error=1.5f;
    bool hlod=true;
    int cluster_size=32; // HLOD cluster
};
HLOD select_lod(float distance, float screen_error, float importance, uint32_t vram_mb, int observer_mode);
float screen_space_error(float dist, float size, float fov, uint32_t h);
std::string hlod_note();
uint32_t cluster_count_for_lod(HLOD lod);
}
