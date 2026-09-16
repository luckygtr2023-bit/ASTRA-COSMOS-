
#include "spatial_audio.h"
#include <cmath>
namespace astra::audio::spatial {
float distance_attenuation(const scene::WorldPos& src, const Listener& lst, bool in_atmo){
 double dx=src.x-lst.pos.x, dy=src.y-lst.pos.y, dz=src.z-lst.pos.z;
 double dist=std::sqrt(dx*dx+dy*dy+dz*dz);
 if(in_atmo) return float(1.0/(1.0+dist*0.001));
 return float(1.0/(1.0+dist*1e-6));
}
float doppler_shift(float base, const scene::WorldPos& sv, const Listener& lst){
 double vsv = std::sqrt(sv.x*sv.x+sv.y*sv.y+sv.z*sv.z);
 double vls = std::sqrt(lst.vel.x*lst.vel.x+lst.vel.y*lst.vel.y+lst.vel.z*lst.vel.z);
 double beta = (vsv - vls)/299792458.0;
 return float(base * (1.0 - beta));
}
float occlusion(const scene::WorldPos&, const scene::WorldPos&){ return 1.0f; }
}
