#version 450
#extension GL_GOOGLE_include_directive : enable
#include "common/common.glsl"
layout(set=0,binding=0) uniform Params { vec3 bh_pos; float rs; } p;
layout(location=0) in vec3 wpos;
layout(location=0) out vec4 outColor;
void main(){ vec3 dr=wpos-p.bh_pos; float r=length(dr); float tidal=2.0*p.rs/(r*r*r+1.0); vec3 col=vec3(0.2,0.5,1.0)*tidal*10.0; outColor=vec4(col,1.0); }
