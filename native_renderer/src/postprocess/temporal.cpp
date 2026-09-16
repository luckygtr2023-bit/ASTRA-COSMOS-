#include "temporal.h"
namespace astra::postprocess {
MotionVector compute_motion_vector(float c[3], float p[3], float vp[16]){
    (void)vp;
    return {c[0]-p[0], c[1]-p[1]};
}
bool handles_origin_shift(const TemporalConfig& cfg){ return cfg.history_buffers; }
bool avoids_ghosting(float v){ return v < 1e6f; }
}
