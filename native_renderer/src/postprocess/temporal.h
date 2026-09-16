#pragma once
#include <cstdint>
namespace astra::postprocess {
// TAA / temporal accumulation / motion vectors / history buffers, handles floating-origin shifts
struct TemporalConfig {
    bool taa=true;
    bool accumulation=true;
    bool history_buffers=true;
    bool motion_vectors=true;
    float blend=0.9f;
};
struct MotionVector { float dx, dy; };
MotionVector compute_motion_vector(float curr[3], float prev[3], float view_proj[16]);
bool handles_origin_shift(const TemporalConfig& cfg); // must handle rebasing without ghosting
bool avoids_ghosting(float velocity); // astronomical-scale movement ghosting check
}
