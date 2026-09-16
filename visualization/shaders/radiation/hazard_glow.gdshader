shader_type spatial;
render_mode blend_add, cull_disabled, depth_draw_never;

uniform vec3 hazard_color : source_color = vec3(1.0,0.25,0.1);
uniform float pulse_freq : hint_range(0.0,10.0)=1.8;
uniform float intensity : hint_range(0.0,3.0)=1.0;

void fragment(){
    float pulse = 0.6 + 0.4*sin(TIME*pulse_freq*6.28);
    float nd = dot(normalize(NORMAL), normalize(-VIEW));
    float rim = pow(1.0 - clamp(nd,0.0,1.0), 2.0);
    vec3 col = hazard_color * rim * pulse * intensity;
    ALBEDO = col;
    ALPHA = clamp(rim*1.2,0.0,1.0)*0.7;
    EMISSION = col;
}
