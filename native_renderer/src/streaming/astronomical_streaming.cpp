#include "astronomical_streaming.h"
namespace astra::streaming {
StreamLevel level_for_distance(double d){
    if(d<1e4) return StreamLevel::LOCAL_OBJECT;
    if(d<1e6) return StreamLevel::TERRAIN_TILE;
    if(d<1e9) return StreamLevel::PLANET;
    if(d<1e12) return StreamLevel::PLANETARY_SYSTEM;
    if(d<1e15) return StreamLevel::STAR_SYSTEM;
    if(d<1e21) return StreamLevel::GALAXY;
    return StreamLevel::UNIVERSE;
}
float priority_for_stream(const StreamRequest& r){
    // priority = screen_size / distance * visibility * importance * focus
    return r.priority * (1.f/(r.distance+1.f)) * 100.f;
}
bool is_resident(const StreamState& s, const std::string& id){
    for(auto &r: s.resident) if(r==id) return true; return false;
}
std::string hierarchy_note(){ return "Universe->Galaxy->StarSystem->Planetary->Planet->Region->Terrain->Local, only required resident"; }
}
