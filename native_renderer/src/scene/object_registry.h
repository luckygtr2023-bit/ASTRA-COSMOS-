#pragma once
// ASTRA Phase01 — Object & Scene Registry (ECS-lite)
// Mirrors astra.world.hierarchy + object states, deterministic seed, streaming budget

#include "floating_origin.h"
#include <string>
#include <vector>
#include <unordered_map>
#include <cstdint>

namespace astra::scene {

struct RegistryObject {
    std::string id;
    std::string kind; // STAR, PLANET, SPACECRAFT, ASTEROID, BLACK_HOLE
    WorldPos world_pos{0,0,0};
    std::array<float,3> relative_pos{0,0,0}; // updated via rebase
    std::string frame = "world";
    std::string classification = "SIMULATED"; // REAL/THEORETICAL/SPECULATIVE
    float mass_kg = 0;
    float radius = 1.f;
    int lod = 0;
    bool visible = true;
    uint32_t streaming_tile = 0;
};

class ObjectRegistry {
public:
    void add(const RegistryObject& o) { objects_[o.id]=o; }
    void remove(const std::string& id) { objects_.erase(id); }
    RegistryObject* find(const std::string& id) { auto it=objects_.find(id); return it==objects_.end()? nullptr : &it->second; }
    size_t size() const { return objects_.size(); }
    void clear() { objects_.clear(); }

    // Update relative positions after origin rebase (floating-origin hook)
    void update_relative(const WorldPos& origin) {
        for(auto& [id,obj] : objects_){
            obj.relative_pos = OriginRebaser::world_to_relative(obj.world_pos, origin);
        }
    }

    // LOD assignment (0-4 → CULLED)
    int compute_lod(const RegistryObject& o, float dist) const {
        if(dist < 5.f) return 0;
        if(dist < 50.f) return 1;
        if(dist < 500.f) return 2;
        if(dist < 5000.f) return 3;
        return 4; // CULLED beyond 5k at LOW
    }

    // Streaming: 256KB tile, 4MB/frame budget — returns tiles to load this frame
    std::vector<uint32_t> streaming_tiles_this_frame(uint32_t budget_bytes = 4*1024*1024) const;

    std::vector<RegistryObject> all() const {
        std::vector<RegistryObject> out; out.reserve(objects_.size());
        for(auto& kv: objects_) out.push_back(kv.second);
        return out;
    }

private:
    std::unordered_map<std::string, RegistryObject> objects_;
};

class SceneRegistry {
public:
    ObjectRegistry objects;
    // Scene-level diagnostics
    struct Stats { size_t object_count=0, visible_count=0, culled_count=0; };
    Stats stats() const;
};

} // namespace astra::scene
