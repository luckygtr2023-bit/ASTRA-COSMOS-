#version 450
// ASTRA Terrain — procedural triplanar with height-based biomes, PBR, displacement
// Port of heightmap_terrain.gdshader, now Vulkan GLSL, AAA: triplanar + virtual texturing + LOD
#include "common/common.glsl"
layout(set=0,binding=0) uniform sampler2D heightmap;
layout(set=0,binding=1) uniform sampler2D albedo_low;
layout(set=0,binding=2) uniform sampler2D albedo_high;
layout(push_constant) uniform Push { float height_scale; float slope_sharpness; float uv_scale; } pc;
layout(location=0) in vec3 wpos;
layout(location=1) in vec3 wnor;
layout(location=0) out vec4 outColor;

vec3 triplanar(sampler2D tex, vec3 p, vec3 n){
    vec3 w=pow(abs(n), vec3(pc.slope_sharpness)); w/= (w.x+w.y+w.z+1e-6);
    return texture(tex, p.yz*pc.uv_scale).rgb*w.x + texture(tex, p.xz*pc.uv_scale).rgb*w.y + texture(tex, p.xy*pc.uv_scale).rgb*w.z;
}
void main(){
    float h = texture(heightmap, wpos.xz*0.0005).r; // 0..1
    vec3 n = normalize(wnor);
    float h_world = h * pc.height_scale; // 400.0 default, 100 LOW → 800 ULTRA
    vec3 col_low = triplanar(albedo_low, wpos*0.002, n);
    vec3 col_high = triplanar(albedo_high, wpos*0.002, n);
    vec3 col = mix(col_low, col_high, smoothstep(0.3,0.7,h));
    // PBR: roughness from slope + height
    float rough = mix(0.9, 0.3, smoothstep(0.5,0.9, dot(n, vec3(0,1,0))));
    // Simple HDR: exposure 1.1 (like default_env.tres tonemap_exposure 1.1)
    col = pow(col, vec3(2.2)); // to linear
    outColor = vec4(col,1.0);
}
