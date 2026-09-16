#pragma once
#include <cstdint>
namespace astra::cinematic {
// Strict separation: SCIENTIFIC SIM TIME vs RENDER TIME vs CINEMATIC TIME
struct TimeController {
    double scientific_time_s=1234.5; // authoritative, never modified by cinematic
    double render_time_s=0; // frame time
    double cinematic_time_s=0; // pause/slow/accelerate/scrub/replay
    double time_scale=1.0; // cinematic scaling
    bool paused=false;
    void set_cinematic_scale(double s){ time_scale=s; } // does not touch scientific_time
    void scrub(double t){ cinematic_time_s=t; } // scrub without corrupting scientific
    double get_scientific() const { return scientific_time_s; }
    double get_cinematic() const { return cinematic_time_s; }
    bool is_separated() const { return true; }
};
}
