shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_disabled;

// ASTRA Spacetime Grid — visualizes curvature via height displacement (not metric solver)
uniform float curvature_strength : hint_range(0.0, 8.0)=1.6;
uniform vec3 well_color : source_color = vec3(0.2,0.5,0.95);
uniform sampler2D height_noise : hint_default_white;

void vertex(){
    float r = length(VERTEX.xz);
    float well = curvature_strength / max(r*0.2, 0.6);
    VERTEX.y -= well;
    NORMAL = normalize(vec3(-well*VERTEX.x*0.02, 1.0, -well*VERTEX.z*0.02));
}

void fragment(){
    float r = length(VERTEX.xz);
    float grid = step(0.92, fract(r*0.2)) + step(0.92, fract(atan(VERTEX.z,VERTEX.x)*8.0/6.28));
    vec3 col = well_color * (0.6 + 0.4*texture(height_noise, UV*4.0).r) + vec3(grid*0.5);
    ALBEDO = col;
}
