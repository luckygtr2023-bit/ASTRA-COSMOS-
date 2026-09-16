#ifndef ASTRA_COMMON_GLSL
#define ASTRA_COMMON_GLSL
// ASTRA Native — common.glsl 13+ lines, port of common_lib.gdshaderinc
// Include via #include "common/common.glsl" in all shaders
#define PI 3.14159265359

float astra_hash(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7)))*43758.5453); }
float astra_hash3(vec3 p){ return fract(sin(dot(p, vec3(127.1,311.7,74.7)))*43758.5453); }
float astra_fbm(vec2 p){ float n=astra_hash(p); n+=0.5*astra_hash(p*2.0); n+=0.25*astra_hash(p*4.0); return n/1.75; }
float astra_fbm3(vec3 p){ return mix(astra_hash3(p), astra_hash3(p*2.0), 0.5); }
vec3 astra_blackbody(float t){ // t 0..1 (2000K→40000K) → RGB, same as star_temperature_lut.ppm 16x256
    float r=clamp(1.0-pow(max(t-0.2,0.0)/0.8,0.6),0.2,1.0);
    float g=clamp(pow(t,0.45),0.2,1.0);
    float b=clamp(pow(t*1.1,0.8),0.2,1.0);
    return vec3(r,g,b);
}
float astra_luminance(vec3 c){ return dot(c, vec3(0.299,0.587,0.114)); }
// Ray-sphere for BH
bool ray_sphere(vec3 ro, vec3 rd, vec3 ce, float r, out float t0, out float t1){
    vec3 oc=ro-ce; float b=dot(oc,rd); float c=dot(oc,oc)-r*r; float h=b*b-c;
    if(h<0.0) return false; h=sqrt(h); t0=-b-h; t1=-b+h; return true;
}
// Deflection helper for lensing alpha≈2r_s/b
vec3 deflect(vec3 dir, vec3 to_center, float rs, float b){
    float alpha = 2.0*rs/max(b,0.001);
    return normalize(dir + to_center*alpha);
}
#endif
