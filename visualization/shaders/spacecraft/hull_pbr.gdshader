shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley;

uniform sampler2D albedo_tex : hint_default_white, filter_linear;
uniform sampler2D normal_tex : hint_normal;
uniform sampler2D roughness_tex : hint_default_white;
uniform float panel_wear : hint_range(0.0,1.0)=0.25;

void fragment(){
    vec3 albedo = texture(albedo_tex, UV).rgb;
    vec3 n = texture(normal_tex, UV).rgb*2.0-1.0;
    NORMAL_MAP = n;
    float rough = texture(roughness_tex, UV).r;
    rough = mix(rough, 0.9, panel_wear*0.4);
    ALBEDO = albedo;
    ROUGHNESS = rough;
    METALLIC = 0.15;
    SPECULAR = 0.5;
}
