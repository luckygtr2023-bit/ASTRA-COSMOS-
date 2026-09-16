#pragma once
#include <string>
#include <cstdint>
namespace astra::perf {
// Explicit frame-time telemetry: TARGET vs ESTIMATE vs MEASURED
struct FrameTimes {
    float cpu_ms=0, gpu_ms=0, sim_submit_ms=0, render_graph_ms=0;
    float culling_ms=0, streaming_ms=0, vfx_ms=0, post_ms=0, present_ms=0;
    float total() const { return cpu_ms+gpu_ms+present_ms; }
};
enum class BudgetLabel { TARGET, ESTIMATE, MEASURED };
struct Budget {
    float target_ms=16.6f; // 60fps
    float estimate_ms=5.2f; // HIGH
    float measured_ms=0; // actual via Tracy/VkQueryPool
    BudgetLabel label=BudgetLabel::TARGET;
    std::string report() const;
};
FrameTimes measure_frame(); // via Tracy ZoneScopedN + VkQueryPool
bool is_measured(const Budget& b);
}
