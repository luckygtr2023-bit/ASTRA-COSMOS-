
// Volumetrics — fog 0.004 albedo, nebula, volumetric clouds 2.5D raymarch, 192 slices CINEMATIC
#include <cmath>
namespace astra::volumetrics {
struct FogParams{ float density=0.004f; float albedo[3]={0.6f,0.65f,0.75f}; int slices=64; };
inline FogParams quality_fog(int preset){ // 0 LOW 1 MED 2 HIGH 3 ULTRA 4 CINEMATIC
    if(preset==0) return {0.0f,{0.6f,0.65f,0.75f},0};
    if(preset==2) return {0.004f,{0.6f,0.65f,0.75f},64};
    if(preset==4) return {0.004f,{0.6f,0.65f,0.75f},192};
    return {0.004f,{0.6f,0.65f,0.75f},128};
}
}
