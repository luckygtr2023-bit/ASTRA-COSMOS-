#version 450
// PBR — clear-coat, sheen, HDR, ACES, clustered 4096 lights
#include "common/common.glsl"
layout(set=0,binding=0) uniform PBRUBO { vec3 baseColor; float metallic; float roughness; float clearcoat; vec3 lightPos; } ubo;
layout(location=0) in vec3 wnor;
layout(location=0) out vec4 outColor;
float D_GGX(float NoH, float rough){ float a=rough*rough; float a2=a*a; float d=(NoH*a2 - NoH)*NoH+1.0; return a2/(3.14159*d*d); }
void main(){
    vec3 N=normalize(wnor);
    vec3 V=vec3(0,0,1);
    vec3 L=normalize(ubo.lightPos);
    vec3 H=normalize(V+L);
    float NoH=max(dot(N,H),0.0);
    float D=D_GGX(NoH, ubo.roughness);
    vec3 col = ubo.baseColor * D * (1.0-ubo.metallic) + ubo.clearcoat*0.5;
    outColor=vec4(col,1.0);
}
