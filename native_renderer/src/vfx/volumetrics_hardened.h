#include <string>
#pragma once
#include <cstdint>
namespace astra::vfx {
// Volumetrics hardened: 3D density fields, ray marching, temporal accumulation, adaptive step, empty-space skipping, LOD
struct VolumeConfig {
    uint32_t slices=64; // LOW 0, HIGH 64, ULTRA 128, CINEMATIC 192
    bool temporal_accum=true;
    bool adaptive_step=true;
    bool empty_skip=true;
    float density=0.004f;
};
float ray_march_cost(const VolumeConfig& cfg); // estimate ms
bool is_physically_meaningful(const std::string& medium); // nebula true, smoke in vacuum false unless CINEMATIC
uint32_t slices_for_tier(int tier);
}
