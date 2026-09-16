#version 450
#extension GL_GOOGLE_include_directive : enable
#include "common/common.glsl"
layout(push_constant) uniform Push{ float temp; float intensity; } pc;
layout(location=0) out vec4 outColor;
void main(){ vec3 col=astra_blackbody(pc.temp)*pc.intensity; outColor=vec4(col,1.0); }
