
// Spacetime — grid_curvature height displacement, gravitational potential visualization
#include <cmath>
namespace astra::spacetime {
inline float curvature_height(float rs, float r){ return rs / std::max(r, rs); } // visualize well depth
// Speculative: warp Alcubierre f(r_s) tanh sigma*(r_s±R)
inline float alcubierre_f(float r, float R, float sigma){
    return (std::tanh(sigma*(r+R)) - std::tanh(sigma*(r-R))) / (2*std::tanh(sigma*R));
}
}
