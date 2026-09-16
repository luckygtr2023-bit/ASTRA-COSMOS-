#version 450
#extension GL_GOOGLE_include_directive : enable
#include "common/common.glsl"
layout(location=0) out vec4 outColor;
void main(){ outColor=vec4(0.1,0.3,0.6,1.0); }
