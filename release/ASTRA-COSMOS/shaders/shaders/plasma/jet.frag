#version 450
#extension GL_GOOGLE_include_directive : enable
#include "common/common.glsl"
layout(set=0,binding=0) uniform Params { vec3 dir; float vel_c; float doppler; } p;
layout(location=0) in vec3 wpos;
layout(location=0) out vec4 outColor;
void main(){ float cyl = length(cross(wpos, p.dir)); float along = dot(wpos, p.dir); vec3 col = vec3(0.8,0.3,0.1)*exp(-cyl*2.0)*exp(-along*0.05); col *= pow(p.doppler,2.0); outColor = vec4(col,1.0); }
