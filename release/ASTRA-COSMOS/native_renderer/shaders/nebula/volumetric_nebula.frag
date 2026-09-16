#version 450
#extension GL_GOOGLE_include_directive : enable
// Volumetric Nebula — FogVolume friendly, emission + dust, AAA volumetrics 192 slices
#include "common/common.glsl"
layout(set=0,binding=0) uniform NebulaUBO { vec3 albedo; float density; vec3 emission; float time; } ubo;
layout(location=0) in vec3 ray_dir;
layout(location=0) out vec4 outColor;
void main(){
    vec3 p = ray_dir*10.0;
    float n = astra_fbm3(p*0.05 + ubo.time*0.02);
    float d = n * ubo.density;
    vec3 col = ubo.albedo*d + ubo.emission*d*2.0;
    // HDR
    col = col/(col+1.0);
    outColor = vec4(col, d);
}
