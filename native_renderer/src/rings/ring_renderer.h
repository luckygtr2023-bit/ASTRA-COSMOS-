#pragma once
#include <string>
namespace astra::rings {
struct RingParams {
    double inner_m=7000000, outer_m=14000000;
    float density=0.5f;
    float optical_depth=0.8f;
    bool gaps=true;
    std::string scientific_status="SIMULATED";
};
float ring_density(float radius_norm); // 0..1 procedural with Cassini division
float ring_shadowing(float radius, float sun_angle);
}
