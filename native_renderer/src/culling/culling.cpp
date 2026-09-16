#include <cstdint>
#include <vector>
// Culling — frustum + occlusion + distance, GPU culling indirect, 4MB budget
namespace astra::culling {
struct AABB{ float min[3], max[3]; };
bool frustum_cull(const AABB& a, const float* view_proj){ (void)a; (void)view_proj; return false; }
uint32_t cull_visible(const std::vector<AABB>& bounds){ return (uint32_t)bounds.size()/2; } // stub halves
}
