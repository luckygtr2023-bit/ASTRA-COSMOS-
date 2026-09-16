#pragma once
#include <string>
namespace astra::nebula {
struct NebulaParams {
    float emission=1.0f, absorption=0.5f, density=0.3f, temperature_k=10000;
    std::string scientific_status="SIMULATED";
    bool volumetric_lighting=true;
};
float density_field(float x,float y,float z, uint32_t seed);
}
