#version 450
// Wormhole Throat — Morris-Thorne b(r)=b0²/r, embed z(r), SPECULATIVE watermark
#include "common/common.glsl"
layout(set=0,binding=0) uniform ThroatUBO { float b0; float watermark; vec3 center; } ubo;
layout(location=0) in vec3 wpos;
layout(location=0) out vec4 outColor;
void main(){
    float r = length(wpos.xz);
    float b = ubo.b0*ubo.b0/max(r,0.001);
    float z = sqrt(max(r*r - b*b,0.0));
    vec3 col = mix(vec3(0.2,0.5,1.0), vec3(0.9,0.4,1.0), smoothstep(ubo.b0, ubo.b0*2.0, r));
    if(ubo.watermark>0.5){
        // distinct speculative tint + subtle grid
        col = mix(col, vec3(0.8,0.2,0.9), 0.2);
        float grid = step(0.98, sin(wpos.x*10.0)*sin(wpos.z*10.0));
        col += grid*0.1;
    }
    outColor = vec4(col,1.0);
}
