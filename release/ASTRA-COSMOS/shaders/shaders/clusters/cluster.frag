#version 450
#extension GL_GOOGLE_include_directive : enable
#include "common/common.glsl"
layout(set=0,binding=0) uniform Params { float density; vec3 color; } p;
layout(location=0) in vec2 uv;
layout(location=0) out vec4 outColor;
void main(){ float n=astra_fbm(uv*5.0); vec3 col=p.color*n*p.density; outColor=vec4(col,n); }
