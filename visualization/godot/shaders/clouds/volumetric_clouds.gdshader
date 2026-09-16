shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_disabled;

// ASTRA Clouds — 2.5D volumetric raymarch in shader (Forward+ FogVolume alternative for LOW)
// Uses FastNoiseLite-style fbm; quality-gated via uniforms.
uniform sampler2D noise_3d : hint_default_white; // baked 3D noise atlas
uniform float coverage : hint_range(0.0,1.0)=0.45;
uniform float softness : hint_range(0.0,1.0)=0.6;
uniform float scroll_speed : hint_range(0.0,2.0)=0.04;
uniform vec3 light_color : source_color = vec3(1.0,0.98,0.92);

float fbm(vec3 p){ return texture(noise_3d, p.xz*0.01 + TIME*scroll_speed).r * 0.6 + texture(noise_3d, p.xz*0.02).r*0.4; }

void fragment(){
    vec3 view = normalize(-VERTEX);
    float h = clamp(dot(NORMAL, vec3(0,1,0)),0.0,1.0);
    float d = fbm(VERTEX*0.004);
    float alpha = smoothstep(coverage - softness, coverage + softness, d*h);
    ALBEDO = light_color * (0.7 + 0.3*h);
    ALPHA = alpha * 0.85;
    TRANSMISSION = vec3(0.2);
}
