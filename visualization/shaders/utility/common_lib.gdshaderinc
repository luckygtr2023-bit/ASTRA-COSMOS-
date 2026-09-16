// ASTRA Utility — common lib (include via #include in Godot 4.4 if enabled, else copy)
#ifndef ASTRA_COMMON_LIB
#define ASTRA_COMMON_LIB
float astra_hash(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7)))*43758.5453); }
float astra_fbm(vec2 p){ float n = astra_hash(p); n += 0.5*astra_hash(p*2.0); n += 0.25*astra_hash(p*4.0); return n/1.75; }
vec3 astra_blackbody(float t){ // t 0..1 (2000..40000K) → RGB
    float r = clamp(1.0 - pow(max(t-0.2,0.0)/0.8, 0.6), 0.2,1.0);
    float g = clamp(pow(t,0.45), 0.2,1.0);
    float b = clamp(pow(t*1.1,0.8), 0.2,1.0);
    return vec3(r,g,b);
}
float astra_luminance(vec3 c){ return dot(c, vec3(0.299,0.587,0.114)); }
#endif
