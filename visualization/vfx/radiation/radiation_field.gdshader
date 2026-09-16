shader_type spatial;
render_mode blend_add, cull_disabled;
uniform float pulse : hint_range(0.0,5.0)=2.0;
void fragment(){ float p = 0.5+0.5*sin(TIME*pulse + UV.x*10.0); ALBEDO = vec3(0.2,1.0,0.3)*p*0.6; ALPHA=0.4; }
