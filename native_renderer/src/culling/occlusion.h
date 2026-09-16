#pragma once
#include <cstdint>
namespace astra::culling {
// Hi-Z depth, GPU occlusion tests, hierarchical depth, visibility buffer
struct HiZConfig {
    bool enabled=true;
    uint32_t levels=5;
    bool gpu_tests=true;
};
bool hi_z_occluded(const float* aabb, const float* hiz);
bool gpu_occlusion_test(uint32_t query_id);
float occlusion_cost_vs_save(float cost_ms, float save_ms); // measure
}
