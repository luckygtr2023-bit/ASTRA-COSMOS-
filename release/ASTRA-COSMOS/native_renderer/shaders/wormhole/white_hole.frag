#version 450
#extension GL_GOOGLE_include_directive : enable
#include "common/common.glsl"
layout(set=0,binding=0) uniform Params { float b0; float watermark; vec3 center; } p;
layout(location=0) in vec3 wpos;
layout(location=0) out vec4 outColor;
void main(){
    float r = length(wpos.xz);
    vec3 col = mix(vec3(1.0,0.9,0.5), vec3(0.6,0.2,1.0), smoothstep(p.b0, p.b0*2.0, r));
    if(p.watermark>0.5) col = mix(col, vec3(0.9,0.3,0.9), 0.15); // SPECULATIVE
    outColor = vec4(col, 1.0);
}
