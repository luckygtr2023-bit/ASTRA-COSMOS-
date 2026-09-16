#include "coordinate_bridge.h"
#include <cmath>
namespace astra::scene {
WorldPos CoordinateBridge::hierarchical_world_pos(const std::string& id) const {
    WorldPos acc{0,0,0};
    std::string cur=id;
    for(int i=0;i<10;i++){
        auto it=frames_.find(cur);
        if(it==frames_.end()) break;
        acc.x+=it->second.local[0]; acc.y+=it->second.local[1]; acc.z+=it->second.local[2];
        if(it->second.parent.empty()) break;
        cur=it->second.parent;
    }
    return acc;
}
CoordinateBridge::PrecisionReport CoordinateBridge::diagnose_precision(double scale) const {
    WorldPos sci{scale+5,0,0}; WorldPos org{scale,0,0};
    auto rel = world_to_relative(sci, org);
    float err = std::fabs(rel[0]-5.f);
    bool stable = (scale<1e15) ? err<1e-3 : std::fabs(rel[0])<5000.f;
    return {scale, err, stable};
}
}
