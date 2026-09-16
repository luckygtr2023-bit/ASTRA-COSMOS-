#version 450
// Accretion Disk — Novikov-Thorne T∝r^-3/4, Doppler g^3 beaming, inner edge ISCO
#include "common/common.glsl"
layout(set=0,binding=0) uniform DiskUBO {
    float rs; // Schwarzschild radius 0.3 render units for 10M☉
    float r_in; // ISCO 3rs
    float r_out; // 8rs
    float watermark; // 0 REAL, 1 SPECULATIVE
    vec3 center;
} ubo;
layout(location=0) in vec3 wpos;
layout(location=0) out vec4 outColor;
void main(){
    float r = length(wpos.xz);
    if(r < ubo.r_in || r > ubo.r_out) discard;
    // Temperature Novikov-Thorne
    float T = pow(ubo.r_out/r, 0.75) * 1e4; // 10kK at inner
    vec3 col = astra_blackbody(clamp((T-2000.0)/38000.0,0.0,1.0));
    // Doppler beaming: g = 1/(gamma*(1 - v·n)), here approximated via keplerian v~sqrt(rs/2r)
    float v = sqrt(ubo.rs/(2.0*r));
    float cos_theta = normalize(wpos).x; // simplified viewing angle
    float g = 1.0/(sqrt(1.0-v*v)*(1.0 - v*cos_theta + 1e-6));
    col *= pow(g,3.0);
    // Watermark for SPECULATIVE vs THEORETICAL distinction
    if(ubo.watermark>0.5) col = mix(col, vec3(0.8,0.2,0.8), 0.15);
    outColor = vec4(col,1.0);
}
