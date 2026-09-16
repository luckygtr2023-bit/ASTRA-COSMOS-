shader_type spatial;
render_mode blend_add, cull_disabled, depth_draw_never;

// ASTRA Celestial — Star Corona (physically-inspired, visualization only)
// Source: ASTRA original, MIT. Visualizes astra.celestial classification via temperature→color LUT.
// Authority: color comes from ASTRA star_temperature; shader never invents spectral class.
uniform sampler2D temperature_lut : hint_default_white, filter_linear;
uniform float temperature_k : hint_range(2000.0, 40000.0) = 5778.0;
uniform float corona_intensity : hint_range(0.0, 3.0) = 1.0;
uniform float limb_darkening : hint_range(0.0, 1.0) = 0.4;

varying vec3 world_dir;

void vertex() {
    world_dir = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
    float ndv = dot(normalize(NORMAL), normalize(-VIEW));
    float fresnel = pow(1.0 - clamp(ndv, 0.0, 1.0), 3.0);
    float t_norm = clamp((temperature_k - 2000.0) / 38000.0, 0.0, 1.0);
    vec3 star_color = texture(temperature_lut, vec2(t_norm, 0.5)).rgb;
    // limb darkening approx: 1 - u*(1 - mu)
    float mu = clamp(ndv, 0.0, 1.0);
    float dark = 1.0 - limb_darkening * (1.0 - mu);
    vec3 col = star_color * dark + star_color * fresnel * corona_intensity * 1.5;
    ALBEDO = col;
    ALPHA = clamp(fresnel * 1.2 + 0.15, 0.0, 1.0);
    EMISSION = col * corona_intensity * 0.6;
}
