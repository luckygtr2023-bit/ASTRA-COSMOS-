shader_type spatial;
render_mode blend_add, cull_disabled, depth_draw_never;

// ASTRA Wormhole Throat — Morris-Thorne flare visualization (SPECULATIVE tag)
// Projects interior view via uv distortion; throat radius from ASTRA wormhole param.
uniform sampler2D interior_view : hint_default_white, filter_linear, repeat_disable;
uniform float throat_radius : hint_range(0.1, 10.0)=1.0;
uniform float flare : hint_range(0.0,1.0)=0.35;
uniform float chromatic : hint_range(0.0,0.02)=0.008;

void fragment(){
    vec2 uv = UV*2.0 -1.0;
    float r = length(uv);
    // flare-out: b(r) / r mapping
    float b = throat_radius / max(r*throat_radius + 0.1, 0.2);
    float dist = b * (1.0 + flare);
    vec2 d = normalize(uv+vec2(0.0001));
    vec3 col;
    col.r = texture(interior_view, 0.5 + d*(r*0.5 + chromatic)).r;
    col.g = texture(interior_view, 0.5 + d*(r*0.5)).g;
    col.b = texture(interior_view, 0.5 + d*(r*0.5 - chromatic)).b;
    float rim = exp(-pow((r - 0.45)/0.08,2.0));
    col += vec3(0.6,0.8,1.0) * rim * 0.7;
    ALBEDO = col;
    ALPHA = clamp(1.0 - smoothstep(0.0, 0.2, r-0.8),0.0,1.0);
    EMISSION = col*0.6;
}
