#version 450
// Procedural Starfield — port of procedural_starfield.gdshader, AAA: density + twinkle
#include "common/common.glsl"
layout(push_constant) uniform Push { float density; float twinkle_speed; float exposure; } pc;
layout(location=0) in vec2 uv;
layout(location=0) out vec4 outColor;
void main(){
    vec2 p = uv*100.0;
    float n = astra_hash(p);
    float star = step(1.0-pc.density*0.01, n);
    float tw = sin(astra_hash(p+vec2(pc.twinkle_speed))*6.28 + pc.twinkle_speed*10.0)*0.2+0.8;
    vec3 col = astra_blackbody(n)*star*tw*pc.exposure;
    // HDR bloom will handle
    outColor = vec4(col, star);
}
