#include "timeline.h"
namespace astra::cinematic {
std::string Timeline::at_time(double t) const {
    for(auto &k: keys) if(k.time_s<=t) return k.value;
    return "";
}
std::string example_timeline(){
    return "T0:camera pos T1:focus Sun T2:time scale 2x T3:flare VFX T4:transition T5:return observer";
}
}
