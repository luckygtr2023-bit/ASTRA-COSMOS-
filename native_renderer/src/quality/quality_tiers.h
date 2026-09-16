#pragma once
// ASTRA Phase01 — Quality Tiers + Capability Detection
// ULTRA / HIGH / MEDIUM / LOW / SAFE — auto-select based on VRAM, features, headless

#include <string>
#include "../rhi/vulkan_rhi.h"

namespace astra::quality {

enum class Tier { CINEMATIC, ULTRA, HIGH, MEDIUM, LOW, SAFE };

struct TierDesc {
    Tier tier = Tier::HIGH;
    std::string name = "HIGH";
    uint32_t shadow_atlas = 4096;
    uint32_t max_lights = 4096;
    uint32_t volumetric_slices = 64;
    uint32_t star_count = 10000;
    uint32_t max_steps_bh = 128;
    float height_scale = 400.f;
    bool hdr = true;
    bool bindless = true;
    bool compute_culling = true;
    bool volumetrics = true;
};

inline TierDesc detect_tier(const rhi::DeviceInfo& info, bool headless) {
    TierDesc d;
    if (headless) {
        d.tier = Tier::SAFE; d.name="SAFE (headless)"; d.shadow_atlas=1024; d.max_lights=512; d.volumetric_slices=16; d.star_count=2048; d.max_steps_bh=64; d.height_scale=100; d.hdr=false; d.bindless=false; return d;
    }
    if (info.vram_mb >= 20000 && info.features.descriptorIndexing) {
        d.tier=Tier::CINEMATIC; d.name="CINEMATIC"; d.shadow_atlas=8192; d.volumetric_slices=256; d.star_count=50000; d.max_steps_bh=512; d.height_scale=1000; d.hdr=true; d.bindless=true;
    } else if (info.vram_mb >= 12000 && info.features.descriptorIndexing) {
        d.tier=Tier::ULTRA; d.name="ULTRA"; d.shadow_atlas=8192; d.volumetric_slices=192; d.star_count=20000; d.max_steps_bh=256; d.height_scale=800;
    } else if (info.vram_mb >= 8000) {
        d.tier=Tier::HIGH; d.name="HIGH"; d.shadow_atlas=4096; d.volumetric_slices=64; d.star_count=10000; d.max_steps_bh=128;
    } else if (info.vram_mb >= 4000) {
        d.tier=Tier::MEDIUM; d.name="MEDIUM"; d.shadow_atlas=2048; d.max_lights=2048; d.volumetric_slices=32; d.star_count=5000; d.max_steps_bh=64; d.height_scale=200;
    } else {
        d.tier=Tier::LOW; d.name="LOW"; d.shadow_atlas=1024; d.max_lights=1024; d.volumetric_slices=16; d.star_count=2048; d.max_steps_bh=32; d.height_scale=100; d.hdr=false;
    }
    // Capability downgrade
    if (!info.features.descriptorIndexing) d.bindless = false;
    return d;
}

} // namespace astra::quality
