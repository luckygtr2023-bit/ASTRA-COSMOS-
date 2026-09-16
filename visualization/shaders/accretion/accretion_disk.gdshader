shader_type spatial;
render_mode blend_add, cull_disabled, depth_draw_always, unshaded;

// ASTRA Accretion Disk — physically-inspired but visualization-only
// Color from temperature profile T~r^{-3/4}; Doppler beaming via view/L.
uniform float inner_radius : hint_range(0.1, 3.0)=1.2;
uniform float outer_radius : hint_range(3.0, 20.0)=10.0;
uniform float temperature_scale : hint_range(0.5,4.0)=1.0;
uniform vec3 inner_color : source_color = vec3(1.0,0.95,0.8);
uniform vec3 outer_color : source_color = vec3(0.6,0.2,0.02);
uniform float doppler_strength : hint_range(0.0,1.0)=0.5;
uniform sampler2D noise : hint_default_white;

void fragment(){
    vec2 p = UV*2.0 -1.0;
    float r = length(p)* outer_radius;
    if(r < inner_radius || r > outer_radius){ ALPHA=0.0; discard; }
    float t_norm = pow(inner_radius / max(r,0.1), 0.75) * temperature_scale;
    vec3 col = mix(outer_color, inner_color, clamp(t_norm,0.0,1.0));
    // Doppler: approaching side brighter
    float doppler = dot(normalize(vec3(p.x,0.0,p.y)), normalize(vec3(1.0,0.0,0.3)));
    col *= 1.0 + doppler * doppler_strength * (1.0 - texture(noise, UV*4.0).r*0.3);
    float alpha = smoothstep(inner_radius, inner_radius*1.1, r) * smoothstep(outer_radius, outer_radius*0.85, r);
    ALBEDO = col;
    ALPHA = alpha * (0.6 + 0.4*texture(noise, UV*8.0+TIME*0.01).r);
    EMISSION = col * alpha * 1.2;
}
