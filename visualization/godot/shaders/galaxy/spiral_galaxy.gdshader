shader_type spatial;
render_mode blend_add, cull_disabled, depth_draw_never;

// ASTRA Galaxy — procedural logarithmic spiral (density wave visualization)
uniform float arm_count : hint_range(1.0,4.0)=2.0;
uniform float arm_tightness : hint_range(0.1,0.6)=0.22;
uniform float arm_width : hint_range(0.01,0.3)=0.08;
uniform vec3 core_color : source_color = vec3(1.0,0.9,0.6);
uniform vec3 arm_color : source_color = vec3(0.6,0.7,1.0);
uniform float core_radius : hint_range(0.0,0.5)=0.18;

void fragment(){
    vec2 p = UV*2.0 - 1.0;
    float r = length(p);
    float theta = atan(p.y, p.x);
    float spiral = 0.0;
    for(float i=0.0;i<4.0;i++){
        if(i >= arm_count) break;
        float offset = i/ arm_count * 6.283;
        float arg = theta + offset + log(max(r,0.001))* (1.0/arm_tightness);
        float arm = exp(-pow(abs(sin(arg))* r / arm_width, 2.0));
        spiral = max(spiral, arm);
    }
    float core = exp(-pow(r/core_radius,2.0));
    vec3 col = mix(arm_color, core_color, core*0.7) * spiral;
    col += core_color * core * 0.5;
    ALBEDO = col;
    ALPHA = clamp(spiral*0.9 + core*0.6, 0.0, 1.0);
    EMISSION = col * 1.4;
}
