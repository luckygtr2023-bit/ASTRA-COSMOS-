shader_type spatial;
render_mode blend_add, cull_disabled;
uniform float open : hint_range(0.0,1.0)=0.0;
void fragment(){ float r = length(UV*2.0-1.0); float a = smoothstep(open*0.8, open, 1.0-r); ALBEDO = vec3(0.6,0.8,1.0)*a; ALPHA=a; }
