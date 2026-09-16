shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_lambert, specular_disabled;

// ASTRA Atmosphere — Rayleigh + Mie approx (O'Neil 2004 simplified, public domain)
// Visualizes atmosphere thickness from ASTRA world; does not compute climate.
uniform vec3 rayleigh_color : source_color = vec3(0.33, 0.58, 0.95);
uniform vec3 mie_color : source_color = vec3(0.95, 0.88, 0.72);
uniform float rayleigh_strength : hint_range(0.0, 3.0) = 1.0;
uniform float mie_strength : hint_range(0.0, 2.0) = 0.6;
uniform float thickness : hint_range(0.0, 4.0) = 1.0;
uniform float horizon_pow : hint_range(1.0, 16.0) = 3.0;

varying vec3 world_n;

void vertex(){ world_n = (MODEL_MATRIX * vec4(NORMAL,0.0)).xyz; }

void fragment(){
    vec3 n = normalize(world_n);
    vec3 v = normalize(-VERTEX);
    float nv = clamp(dot(n, v), 0.0, 1.0);
    float rayleigh = pow(1.0 - nv, horizon_pow) * rayleigh_strength * thickness;
    float mie = pow(nv, 8.0) * mie_strength * thickness;
    vec3 col = rayleigh * rayleigh_color + mie * mie_color;
    ALBEDO = col;
    ALPHA = clamp((rayleigh + mie*0.4) * 1.1, 0.0, 1.0);
    // night-side: fade by NdotL (requires LIGHT evaluation in Godot, expose as vertex color)
}
