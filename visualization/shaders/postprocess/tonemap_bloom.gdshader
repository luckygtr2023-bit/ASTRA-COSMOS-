shader_type canvas_item;
render_mode blend_mix;

// ASTRA Postprocess — AgX-inspired tonemap + subtle bloom (Forward+ CompositorEffect adapter)
uniform sampler2D screen : hint_screen_texture, filter_linear;
uniform float exposure : hint_range(0.1, 4.0)=1.15;
uniform float bloom_strength : hint_range(0.0,1.5)=0.35;
uniform float bloom_threshold : hint_range(0.5,2.0)=1.05;
uniform float saturation : hint_range(0.0,2.0)=1.02;

vec3 agx_tonemap(vec3 c){
    // AgX approx via  curve; not full ACES, intentionally subtle for scientific contrast
    c *= exposure;
    c = (c * (2.51*c + 0.03)) / (c * (2.43*c + 0.59) + 0.14);
    return pow(c, vec3(1.0/1.1));
}

void fragment(){
    vec3 col = texture(screen, SCREEN_UV).rgb;
    float lum = dot(col, vec3(0.299,0.587,0.114));
    float bloom = smoothstep(bloom_threshold, bloom_threshold+0.8, lum) * bloom_strength;
    // simple 3x3 bloom blur (single tap feathered for performance on LOW; HIGH uses compute)
    vec2 ps = SCREEN_PIXEL_SIZE;
    vec3 blur = texture(screen, SCREEN_UV + ps*1.0).rgb *0.12 + texture(screen, SCREEN_UV - ps*1.0).rgb*0.12;
    col = col + blur*bloom;
    col = agx_tonemap(col);
    col = mix(vec3(dot(col, vec3(0.333))), col, saturation);
    COLOR = vec4(col, 1.0);
}
