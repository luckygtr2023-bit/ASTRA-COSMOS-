#version 450
// Doppler + beaming + redshift — spectral shift via blackbody LUT 16×256
#include "common/common.glsl"
layout(set=0,binding=0) uniform DopplerUBO { float vel; float cos_theta; float temp_k; } ubo;
layout(location=0) out vec4 outColor;
void main(){
    float g = 1.0/(sqrt(1.0-ubo.vel*ubo.vel)*(1.0 - ubo.vel*ubo.cos_theta));
    float beaming = pow(g,3.0);
    float t_norm = clamp((ubo.temp_k*g -2000.0)/38000.0,0.0,1.0);
    vec3 col = astra_blackbody(t_norm)*beaming;
    outColor=vec4(col,1.0);
}
