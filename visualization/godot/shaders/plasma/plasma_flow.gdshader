shader_type spatial;
render_mode blend_add, cull_disabled, depth_draw_never;

uniform vec3 color_core : source_color = vec3(0.2,0.6,1.0);
uniform vec3 color_edge : source_color = vec3(0.8,0.15,0.9);
uniform float flow_speed : hint_range(0.0,4.0)=1.1;
uniform float turbulence : hint_range(0.0,1.0)=0.55;
uniform sampler2D flow_noise : hint_default_white;

void fragment(){
    vec2 uv = UV;
    uv.x += TIME*flow_speed*0.08;
    float n = texture(flow_noise, uv*2.0).r;
    float n2 = texture(flow_noise, uv*3.7 + vec2(TIME*0.03,0.0)).r;
    float f = n*0.6 + n2*0.4;
    f = pow(f, 1.0 + turbulence);
    vec3 col = mix(color_edge, color_core, f);
    ALBEDO = col;
    ALPHA = smoothstep(0.15,0.9,f) * 0.85;
    EMISSION = col * (0.8 + f*0.6);
}
