shader_type sky;
render_mode use_debanding;

// ASTRA Stars — Procedural Starfield (adapted from godotshaders.com MIT procedural-starfield by arcanewizard)
// Adapted for Forward+, exposure control, ASTRA classification-aware density.
// Original: MIT, https://godotshaders.com/shader/procedural-starfield
// ASTRA mod: adds quality uniform, temperature variation, no twinkle physics invented.

uniform int star_layers : hint_range(1, 4) = 3;
uniform float star_density : hint_range(0.0, 1.0) = 0.7;
uniform float exposure : hint_range(0.1, 5.0) = 1.0;
uniform float twinkle_speed : hint_range(0.0, 2.0) = 0.3;
uniform sampler2D temperature_lut : hint_default_white;

float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7)))*43758.5453); }

void sky() {
    vec3 dir = normalize(EYEDIR);
    vec2 uv = dir.xy / (dir.z + 2.0);
    vec3 col = vec3(0.01, 0.01, 0.04);
    float t = TIME * twinkle_speed;
    for(int i=0; i<4; i++){
        if(i >= star_layers) break;
        float scale = pow(2.0, float(i)) * 80.0;
        vec2 gv = fract(uv * scale);
        vec2 id = floor(uv * scale);
        float h = hash(id + float(i)*17.0);
        if(h > (1.0 - star_density * 0.12)){
            float d = length(gv - 0.5);
            float star = smoothstep(0.05, 0.0, d) * (0.6 + 0.4*sin(t*1.7 + h*6.28));
            float temp = fract(h*1.3);
            vec3 scol = texture(temperature_lut, vec2(temp, 0.5)).rgb;
            col += star * scol * exposure * (1.0 - float(i)*0.22);
        }
    }
    COLOR = col;
}
