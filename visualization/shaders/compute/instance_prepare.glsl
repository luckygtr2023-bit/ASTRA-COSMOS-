#[compute]
#version 450
// ASTRA Compute — instance buffer preparation (10k stars, 60+ fps)
// Prepares MultiMeshInstance3D buffer from ASTRA RenderState on GPU; no CPU loop.
// Invoked via RenderingDevice, Forward+ only. CPU fallback exists.
layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;
layout(set = 0, binding = 0, std430) restrict buffer Positions {
    vec4 pos_scale[]; // xyz = world pos (after floating origin), w = scale/lod
} positions;
layout(set = 0, binding = 1, std430) restrict buffer Inputs {
    vec4 in_pos[]; // from ASTRA bridge
} inputs;
layout(set = 0, binding = 2) uniform Params {
    vec3 origin_offset;
    float count;
} params;

void main(){
    uint id = gl_GlobalInvocationID.x;
    if(id >= uint(params.count)) return;
    vec3 p = inputs.in_pos[id].xyz - params.origin_offset;
    float lod = length(p) > 50000.0 ? 1.0 : 0.0;
    positions.pos_scale[id] = vec4(p, mix(1.0, 0.4, lod));
}
