#include "diagnostics.h"
#include <cstdio>
namespace astra::diagnostics {
void DiagnosticsOverlay::print() const {
    std::printf("[DiagnosticsOverlay] fps=%.1f gpu=%.2fms draw=%u vram=%u/%u shaders %u/%u stable=%d\n",
        frame.fps, gpu.total_ms, resources.draw_calls, resources.vram_used_mb, resources.vram_budget_mb,
        shaders.compiled, shaders.compiled+shaders.failed, coords.stable);
}
std::string DiagnosticsOverlay::to_json() const {
    return "{\"fps\":"+std::to_string(frame.fps)+",\"gpu_ms\":"+std::to_string(gpu.total_ms)+"}";
}
}
