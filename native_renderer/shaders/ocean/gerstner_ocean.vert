#version 450
// Gerstner Ocean — 4-wave Gerstner, PBR, displacement, AAA
#include "common/common.glsl"
layout(set=0,binding=0) uniform OceanUBO { float time; float wave_scale; float choppy; vec2 wind; } ubo;
layout(location=0) in vec3 inPos;
layout(location=1) in vec3 inNor;
layout(location=0) out vec3 wpos;
layout(location=1) out vec3 wnor;
vec3 gerstner(vec3 p){
    vec3 res=p;
    for(int i=0;i<4;i++){
        float k = 0.1+float(i)*0.07;
        float a = 0.5/(float(i)+1.0);
        float w = 1.0 + float(i)*0.3;
        float phase = k*dot(normalize(vec2(1,0.5)), p.xz) - w*ubo.time;
        res.x += a*cos(phase)*ubo.choppy;
        res.z += a*sin(phase)*ubo.choppy;
        res.y += a*sin(phase);
    }
    return res;
}
void main(){
    vec3 pos = gerstner(inPos*ubo.wave_scale);
    wpos = pos;
    wnor = normalize(cross(dFdx(pos), dFdy(pos)));
    gl_Position = vec4(pos,1.0); // MVP applied in real pipeline
}
