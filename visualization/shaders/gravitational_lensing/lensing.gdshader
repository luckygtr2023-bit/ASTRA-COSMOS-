shader_type canvas_item;
render_mode blend_mix;

// ASTRA Gravitational Lensing — screen-space distortion (visualization of photon-path bending)
// Reads SCREEN_TEXTURE, displaces by mass-dependent radial function. Scientific state (mass, distance) from ASTRA bridge.
uniform sampler2D screen : hint_screen_texture, filter_linear;
uniform vec2 center : hint_position = vec2(0.5,0.5);
uniform float mass_strength : hint_range(0.0, 0.5)=0.08; // ~2GM/(c^2 r) scaled for viz
uniform float photon_ring_radius : hint_range(0.01,0.3)=0.08;
uniform float vignette : hint_range(0.0,1.0)=0.4;

void fragment(){
    vec2 uv = FRAGCOORD.xy / SCREEN_PIXEL_SIZE.xy / vec2(textureSize(screen,0));
    vec2 d = uv - center;
    float r = length(d);
    float rs = photon_ring_radius;
    // simple Schwarzschild deflection: alpha ~ rs / r
    float deflection = mass_strength / max(r, 0.005);
    vec2 uv_lensed = uv + normalize(d+vec2(0.0001)) * deflection * exp(-pow(r/rs,2.0)*0.5);
    vec3 col = texture(screen, uv_lensed).rgb;
    // photon ring highlight
    float ring = exp(-pow((r - rs)/0.015,2.0)) * 0.9;
    col += vec3(1.0,0.9,0.7) * ring;
    // vignette preserves contrast
    col *= 1.0 - vignette * pow(r,1.5);
    COLOR = vec4(col, 1.0);
}
