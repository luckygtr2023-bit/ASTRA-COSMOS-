#include <cmath>
// Planetary Renderer — PBR spheroid, triplanar, HLOD, virtual texturing
namespace astra::planetary {
// Icosphere subdiv LOD 2→5 : 42→10k verts
struct Mesh { int verts; float height_scale; };
Mesh lod_mesh(int lod){
    int verts = 42 << (lod*2); // stub
    float scale = lod==0?100.f : lod==1?400.f : 800.f;
    return {verts, scale};
}
// Atmosphere Rayleigh 4e-6 Mie 2.1e-5
struct AtmosParams { float rayleigh=4e-6f; float mie=2.1e-5f; };
}
