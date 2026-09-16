shader_type spatial;
render_mode blend_mix, depth_draw_opaque;

uniform sampler2D heightmap : hint_default_black;
uniform float crater_depth : hint_range(0.0,50.0)=8.0;
uniform vec3 ejecta_color : source_color = vec3(0.55,0.42,0.33);
uniform float rim_power : hint_range(0.5,8.0)=2.5;

void fragment(){
    float h = texture(heightmap, UV).r;
    float rim = pow(abs(h-0.5)*2.0, rim_power);
    vec3 col = mix(vec3(0.2,0.16,0.12), ejecta_color, rim);
    ALBEDO = col;
    METALLIC = 0.0; ROUGHNESS = 0.85 - rim*0.3;
}
