#include "nebula_renderer.h"
#include <cmath>
namespace astra::nebula {
float density_field(float x,float y,float z, uint32_t s){
    float h = std::sin(x*0.01f + s*1e-6f)* std::cos(y*0.01f) * std::sin(z*0.01f);
    return 0.5f+0.5f*h;
}
}
