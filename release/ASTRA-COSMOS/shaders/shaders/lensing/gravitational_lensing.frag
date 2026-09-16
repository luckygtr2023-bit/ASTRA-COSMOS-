#version 450
#extension GL_GOOGLE_include_directive : enable
// Gravitational Lensing — alpha=4GM/c²b =2r_s/b, Einstein ring theta_E, screen-space distortion
#include "common/common.glsl"
layout(set=0,binding=0) uniform sampler2D sceneColor;
layout(set=0,binding=1) uniform LensingUBO { float rs; float strength; vec2 center_uv; float watermark; } ubo;
layout(location=0) in vec2 uv;
layout(location=0) out vec4 outColor;
void main(){
    vec2 delta = uv - ubo.center_uv;
    float b = length(delta);
    float alpha = 2.0*ubo.rs/max(b,0.001) * ubo.strength;
    vec2 lensed_uv = uv - normalize(delta)*alpha*0.02;
    vec3 col = texture(sceneColor, clamp(lensed_uv,0.0,1.0)).rgb;
    // Einstein ring: b ≈ sqrt(2rs * D) — simplified bright ring at b=0.02
    float ring = exp(-pow(b-0.02,2.0)/0.0001)*0.5;
    col += ring;
    if(ubo.watermark>0.5) col = mix(col, vec3(0.7,0.3,0.9), 0.08);
    outColor = vec4(col,1.0);
}
