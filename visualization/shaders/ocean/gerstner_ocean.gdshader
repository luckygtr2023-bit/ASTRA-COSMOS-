shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley;

// ASTRA Ocean — 4-wave Gerstner (MIT godotshaders.com ocean, adapted)
uniform float wave_scale : hint_range(0.1, 10.0) = 1.0;
uniform float wave_speed : hint_range(0.0, 4.0) = 0.8;
uniform float wave_height : hint_range(0.0, 8.0) = 1.2;
uniform vec4 foam_color : source_color = vec4(0.92,0.95,0.98,1.0);
uniform vec4 water_color : source_color = vec4(0.04, 0.22, 0.38,1.0);
uniform sampler2D foam_tex : hint_default_white;

vec3 gerstner(vec2 p, float t, float s, float amp, vec2 dir){
    float k = 0.8 * s;
    float c = 1.2 * s;
    float f = k*dot(dir,p) - c*t;
    float a = amp / k;
    return vec3(dir.x*a*cos(f), a*sin(f), dir.y*a*cos(f));
}

void vertex(){
    float t = TIME * wave_speed;
    vec3 p = VERTEX;
    vec3 o = vec3(0.0);
    o += gerstner(p.xz, t, 1.0*wave_scale, 0.5*wave_height, normalize(vec2(1.0,0.6)));
    o += gerstner(p.xz, t*1.3, 1.7*wave_scale, 0.3*wave_height, normalize(vec2(-0.7,1.0)));
    o += gerstner(p.xz, t*0.7, 0.6*wave_scale, 0.2*wave_height, normalize(vec2(0.3,-0.9)));
    VERTEX += o;
    NORMAL = normalize(NORMAL + vec3(o.x*0.1, 0.0, o.z*0.1));
}

void fragment(){
    vec3 v = normalize(-VERTEX);
    vec3 n = normalize(NORMAL);
    float fresnel = pow(1.0 - clamp(dot(n,v),0.0,1.0), 5.0);
    vec3 col = mix(water_color.rgb, vec3(0.5,0.75,0.9), fresnel*0.7);
    float foam = texture(foam_tex, UV*4.0).r * fresnel;
    ALBEDO = mix(col, foam_color.rgb, clamp(foam*0.6,0.0,1.0));
    ROUGHNESS = 0.15 + fresnel*0.1;
    SPECULAR = 0.8;
}
