#version 450
#extension GL_GOOGLE_include_directive : enable
#include "common/common.glsl"
layout(set=0,binding=0) uniform Params { vec3 dipole; float strength; } p;
layout(location=0) in vec3 wpos;
layout(location=0) out vec4 outColor;
void main(){ float r = length(wpos); float f = p.strength/(r*r*r+1.0); vec3 col = mix(vec3(0.0,0.2,0.5), vec3(0.2,0.8,1.0), f*2.0); outColor = vec4(col, f); }
