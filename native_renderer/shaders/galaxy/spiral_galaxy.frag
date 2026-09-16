#version 450
#extension GL_GOOGLE_include_directive : enable
// Spiral Galaxy — logarithmic spiral density wave visualization, procedural 2 arms, AAA
#include "common/common.glsl"
layout(push_constant) uniform Push { float arm_count; float tightness; float time; } pc; // tightness b=0.22
layout(location=0) in vec2 uv; // uv centered -1..1
layout(location=0) out vec4 outColor;
void main(){
    vec2 p = uv;
    float r = length(p);
    float theta = atan(p.y,p.x);
    float density=0.0;
    for(float k=0.0;k<pc.arm_count;k++){
        float theta0 = theta + k*6.28/pc.arm_count;
        float spiral = r - exp(pc.tightness*theta0);
        density += exp(-pow(spiral,2.0)/0.02) * exp(-r*1.5);
    }
    vec3 col = vec3(0.6,0.3,0.8)*density + vec3(0.95,0.92,0.85)*density*0.5;
    outColor = vec4(col, density);
}
