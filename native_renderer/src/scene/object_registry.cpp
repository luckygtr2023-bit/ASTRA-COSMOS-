#include "object_registry.h"
namespace astra::scene {
std::vector<uint32_t> ObjectRegistry::streaming_tiles_this_frame(uint32_t budget) const {
    uint32_t tiles = budget / (256*1024);
    std::vector<uint32_t> out;
    size_t n = std::min<size_t>(tiles, objects_.size());
    for(size_t i=0;i<n;i++) out.push_back(uint32_t(i));
    return out;
}
SceneRegistry::Stats SceneRegistry::stats() const {
    Stats s; s.object_count = objects.size();
    for(auto& o: objects.all()){ if(o.visible) s.visible_count++; else s.culled_count++; }
    return s;
}
}
