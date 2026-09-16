shader_type spatial;
render_mode blend_add, depth_draw_never, cull_disabled;

// ASTRA Particles — billboard with soft depth and scattering
uniform sampler2D soft_noise : hint_default_white;
uniform vec3 base_color : source_color = vec3(0.95,0.8,0.5);
uniform float softness : hint_range(0.0,1.0)=0.6;

void fragment(){
    float n = texture(soft_noise, UV).r;
    float a = 1.0 - length(UV*2.0 -1.0);
    a = smoothstep(0.0,0.6,a) * n;
    ALBEDO = base_color;
    ALPHA = a * softness;
    EMISSION = base_color * a * 0.8;
}
