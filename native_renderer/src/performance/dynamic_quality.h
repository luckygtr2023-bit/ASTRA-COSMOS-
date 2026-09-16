#pragma once
#include <cstdint>
namespace astra::perf {
struct DynamicQuality {
    bool enabled=true;
    float budget_ms=16.6f;
    uint32_t resolution_scale=100; // percent
    uint32_t particle_pct=100;
    uint32_t volumetric_pct=100;
    uint32_t shadow_pct=100;
    int lod_bias=0;
    float vfx_density=1.f;
    void adapt(float frame_ms); // reduce if over budget, restore if under
    bool only_render_fidelity() const { return true; } // never modifies simulation fidelity
};
}
