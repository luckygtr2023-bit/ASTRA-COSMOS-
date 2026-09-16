shader_type spatial;
render_mode blend_add, cull_disabled, depth_draw_never;

// ASTRA Nebula — volumetric dust + emission (FogVolume friendly)
uniform sampler2D dust_noise : hint_default_white;
uniform vec3 color_a : source_color = vec3(0.85,0.15,0.55);
uniform vec3 color_b : source_color = vec3(0.15,0.55,0.95);
uniform float density : hint_range(0.0,2.0)=0.8;
uniform float glow : hint_range(0.0,4.0)=1.6;

void fragment(){
    vec2 uv = UV*3.0;
    float n = texture(dust_noise, uv).r;
    float n2 = texture(dust_noise, uv*1.7 + vec2(TIME*0.02,0.0)).r;
    float d = n*0.6 + n2*0.4;
    float alpha = smoothstep(0.35, 0.8, d) * density;
    vec3 col = mix(color_a, color_b, d) * glow;
    ALBEDO = col;
    ALPHA = alpha * 0.6;
    EMISSION = col * alpha * 1.2;
}
