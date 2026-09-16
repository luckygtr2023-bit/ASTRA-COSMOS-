shader_type spatial;
render_mode blend_mix, depth_draw_opaque;

#include "res://shaders/utility/common_lib.gdshaderinc"
// ASTRA Terrain — procedural triplanar with height-based biomes (visualization only)
// Uses astra_hash from common_lib for detail perturbation where needed
uniform sampler2D heightmap : hint_default_black;
uniform sampler2D albedo_low : hint_default_white;
uniform sampler2D albedo_high : hint_default_white;
uniform float height_scale : hint_range(0.0, 2000.0) = 400.0;
uniform float slope_sharpness : hint_range(0.5, 8.0) = 2.0;

varying vec3 wpos;

void vertex(){ wpos = (MODEL_MATRIX * vec4(VERTEX,1.0)).xyz; }

vec3 triplanar(sampler2D tex, vec3 p, vec3 n){
    vec3 w = pow(abs(n), vec3(slope_sharpness));
    w /= (w.x+w.y+w.z);
    return texture(tex, p.yz).rgb * w.x + texture(tex, p.xz).rgb * w.y + texture(tex, p.xy).rgb * w.z;
}

void fragment(){
    float h = texture(heightmap, UV).r;
    vec3 n = normalize(NORMAL);
    float h_world = h * height_scale;
    vec3 col_low = triplanar(albedo_low, wpos*0.002, n);
    vec3 col_high = triplanar(albedo_high, wpos*0.002, n);
    vec3 col = mix(col_low, col_high, smoothstep(0.3, 0.7, h));
    ALBEDO = col;
    // slope darkening
    float slope = 1.0 - abs(dot(n, vec3(0,1,0)));
    ALBEDO *= (1.0 - slope*0.25);
}
