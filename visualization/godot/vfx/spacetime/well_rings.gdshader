shader_type spatial;
render_mode blend_add, cull_disabled;
uniform float ring_speed : hint_range(0.0,3.0)=0.8;
void fragment(){ float r = length(UV*2.0-1.0); float rings = sin(r*20.0 - TIME*ring_speed*6.28)*0.5+0.5; ALBEDO = vec3(0.4,0.6,1.0)*rings; ALPHA = rings*0.5; }
