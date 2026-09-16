#include "ring_renderer.h"
#include <cmath>
namespace astra::rings {
float ring_density(float r){
    float d = 0.5f + 0.5f*std::sin(r*50.0f);
    if(r>0.45f && r<0.48f) d *= 0.1f; // Cassini division
    if(r>0.75f && r<0.78f) d *= 0.2f; // Encke gap
    return d;
}
float ring_shadowing(float, float){ return 0.8f; }
}
