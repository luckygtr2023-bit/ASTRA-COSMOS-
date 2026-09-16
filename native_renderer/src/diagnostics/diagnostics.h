#pragma once
// ASTRA Phase01 — Diagnostics, Telemetry, Debug Rendering
// Frame timing, CPU/GPU timing, draw calls, VRAM, buffer counts, shader errors, sync errors, coordinate precision

#include <string>
#include <vector>
#include <cstdint>

namespace astra::diagnostics {

struct FrameTimings {
    float cpu_ms = 0, gpu_ms = 0, frame_ms = 0;
    float fps = 60.f, avg60 = 60.f;
};

struct GpuTimings {
    float shadow_ms = 0, terrain_ms = 0, atmosphere_ms = 0, stars_ms = 0, galaxy_ms = 0, bh_ms = 0, lensing_ms = 0, vfx_ms = 0, postprocess_ms = 0;
    float total_ms = 0;
};

struct ResourceStats {
    uint32_t draw_calls = 0, triangles = 0, dispatch_count = 0;
    uint32_t vram_used_mb = 0, vram_budget_mb = 4096;
    uint32_t buffer_count = 0, texture_count = 0;
    uint64_t buffer_bytes = 0, texture_bytes = 0;
};

struct ShaderDiagnostics {
    uint32_t compiled = 0, failed = 0, cached = 0;
    std::vector<std::string> errors;
};

struct SyncDiagnostics {
    uint32_t fences = 0, semaphores = 0;
    bool has_validation_errors = false;
    std::vector<std::string> validation_messages;
};

struct CoordinateDiagnostics {
    double world_scale = 1e11;
    float relative_error = 0;
    bool stable = true;
    std::string origin = "0,0,0";
};

struct DiagnosticsOverlay {
    FrameTimings frame;
    GpuTimings gpu;
    ResourceStats resources;
    ShaderDiagnostics shaders;
    SyncDiagnostics sync;
    CoordinateDiagnostics coords;
    void print() const; // ImGui or stdout
    std::string to_json() const;
};

// Tracy + RenderDoc hooks (no-op if not available)
namespace tracy {
    inline void frame_mark(const char* name) { (void)name; /* FrameMark */ }
    inline void zone_begin(const char* name) { (void)name; /* ZoneScopedN */ }
    inline void zone_end() {}
    inline void plot(const char* name, float v) { (void)name; (void)v; }
}
namespace renderdoc {
    inline bool is_capturing() { return false; }
    inline void start_capture() { /* pRENDERDOC_StartFrameCapture */ }
    inline void end_capture() {}
}

} // namespace astra::diagnostics
