#include "dynamic_quality.h"
namespace astra::perf {
void DynamicQuality::adapt(float ms){
    if(!enabled) return;
    if(ms > budget_ms){
        if(resolution_scale>50) resolution_scale-=10;
        if(particle_pct>25) particle_pct-=25;
        if(volumetric_pct>25) volumetric_pct-=25;
        lod_bias++;
    } else if(ms < budget_ms*0.8f){
        if(resolution_scale<100) resolution_scale+=5;
        if(particle_pct<100) particle_pct+=10;
        if(lod_bias>0) lod_bias--;
    }
}
}
