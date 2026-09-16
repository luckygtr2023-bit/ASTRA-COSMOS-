#version 450
#extension GL_GOOGLE_include_directive : enable
// ASTRA Atmosphere — Rayleigh + Mie (O'Neil 2004, simplified), HDR, multiple scattering stub
// Rayleigh 4e-6 Mie 2.1e-5 as in spec, volumetric_fog 0.004 albedo
#include "common/common.glsl"
layout(set=0,binding=0) uniform AtmosphereUBO {
    vec3 sun_dir; float sun_intensity;
    vec3 rayleigh_beta; float mie_beta; // 4e-6 , 2.1e-5
    vec3 albedo; float density;
    float planet_radius; float atmo_radius;
} ubo;
layout(location=0) in vec3 ray_dir;
layout(location=1) in vec3 cam_pos;
layout(location=0) out vec4 outColor;

// Simple optical depth via ray-sphere
void main(){
    vec3 pos = cam_pos;
    vec3 dir = normalize(ray_dir);
    float t0,t1;
    if(!ray_sphere(pos, dir, vec3(0), ubo.atmo_radius, t0, t1)){ discard; }
    t0 = max(t0,0.0);
    vec3 scattering = vec3(0);
    int steps = 16; // 64 ULTRA, 32 HIGH
    float step_len = (t1-t0)/float(steps);
    for(int i=0;i<steps;i++){
        vec3 p = pos + dir*(t0 + step_len*(float(i)+0.5));
        float h = length(p)-ubo.planet_radius;
        float hr = exp(-h/8000.0)*step_len; // Rayleigh scale 8km
        float hm = exp(-h/1200.0)*step_len; // Mie scale 1.2km
        vec3 atten = exp(-(ubo.rayleigh_beta*hr + vec3(ubo.mie_beta)*hm));
        scattering += atten * (ubo.rayleigh_beta*hr + vec3(ubo.mie_beta)*hm) * ubo.sun_intensity;
    }
    vec3 col = scattering * ubo.albedo;
    // HDR + tonemap AgX
    col = col/(col+1.0);
    outColor = vec4(pow(col, vec3(1.0/2.2)), 1.0);
}
