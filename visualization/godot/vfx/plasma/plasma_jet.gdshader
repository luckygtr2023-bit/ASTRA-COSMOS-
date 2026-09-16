shader_type spatial;
render_mode blend_add, cull_disabled;
uniform vec3 jet_color : source_color = vec3(0.3,0.7,1.0);
void fragment(){ float n = UV.y + TIME*0.5; ALBEDO = jet_color * (0.6 + 0.4*sin(n*20.0)); ALPHA = 0.7; EMISSION = ALBEDO*1.2; }
