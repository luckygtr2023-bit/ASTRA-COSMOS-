shader_type spatial;
render_mode blend_add, cull_disabled;
uniform float flare_intensity : hint_range(0.0,3.0)=1.5;
void fragment(){ float f = pow(1.0-length(UV*2.0-1.0), 3.0); ALBEDO = vec3(1.0,0.85,0.4)*f*flare_intensity; ALPHA = f; EMISSION = ALBEDO; }
