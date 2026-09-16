#include "occlusion.h"
namespace astra::culling {
bool hi_z_occluded(const float*, const float*){ return false; }
bool gpu_occlusion_test(uint32_t){ return false; }
float occlusion_cost_vs_save(float c, float s){ return s - c; } // positive means save
}
