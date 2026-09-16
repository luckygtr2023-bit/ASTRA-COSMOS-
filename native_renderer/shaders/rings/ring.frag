#version 450
#extension GL_GOOGLE_include_directive : enable
#include "common/common.glsl"
layout(set=0,binding=0) uniform RingUBO { float inner; float outer; float density; float optical; } ubo;
layout(location=0) in vec2 uv;
layout(location=0) out vec4 outColor;
void main(){ float r=length(uv); float rn=(r-ubo.inner)/(ubo.outer-ubo.inner); float d=0.5+0.5*sin(rn*50.0); if(rn>0.45&&rn<0.48) d*=0.1; if(rn<0.0||rn>1.0) discard; float a=d*ubo.optical; vec3 col=vec3(0.6,0.5,0.4)*d; outColor=vec4(col,a); }
