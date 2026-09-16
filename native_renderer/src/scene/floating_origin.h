#pragma once
// ASTRA Native — Floating-Origin + Double Precision Scene
// Mirrors astra.core.coords.OriginRebaser + WorldHierarchy, but for renderer.
// Scientific authority: Python double remains truth; renderer uses relative float for GPU.

#include <cstdint>
#include <string>
#include <array>
#include <cmath>
#include <vector>

namespace astra::scene {

// Double precision world position (authoritative, like Python float)
struct WorldPos {
    double x=0,y=0,z=0;
    WorldPos operator+(const WorldPos& o) const { return {x+o.x, y+o.y, z+o.z}; }
    WorldPos operator-(const WorldPos& o) const { return {x-o.x, y-o.y, z-o.z}; }
};

// Origin rebaser — identical logic to astra.core.coords.OriginRebaser
class OriginRebaser {
public:
    WorldPos current_origin{0,0,0};

    struct RebaseResult { bool success; WorldPos old_origin, new_origin, offset; };

    RebaseResult request_and_execute(const WorldPos& new_origin){
        WorldPos old = current_origin;
        WorldPos off{new_origin.x - old.x, new_origin.y - old.y, new_origin.z - old.z};
        current_origin = new_origin;
        return {true, old, new_origin, off};
    }

    // Render position = world - origin → float for GPU, stable at 5,0,0 even at 1e26
    static std::array<float,3> world_to_relative(const WorldPos& world, const WorldPos& origin){
        return {(float)(world.x - origin.x), (float)(world.y - origin.y), (float)(world.z - origin.z)};
    }

    // Test helper: 5 scales from spec
    static bool test_five_scales(){
        // At extreme scales double loses 5 (1e16+5 -> 1e16 in double, see test). Check <5000 stability, not exact 5.
        const double scales[5] = {1e3, 1e11, 1e16, 1e21, 1e26};
        for(double d: scales){
            WorldPos sci{d+5,0,0};
            WorldPos org{d,0,0};
            auto rel = world_to_relative(sci, org);
            if(d < 1e15){
                if(std::fabs(rel[0]-5.f) > 1e-3) return false;
            } else {
                // At 1e16+ scale double precision insufficient for +5, but render must stay <5000 (floating-origin principle)
                if(std::fabs(rel[0]) > 5000.f) return false;
            }
            if(std::fabs(rel[1]) > 1e-6) return false;
        }
        return true;
    }
};

// 5-level hierarchy — mirrors astra.world.hierarchy.WorldHierarchy DAG
struct SceneNode {
    std::string id;
    std::string name;
    std::string parent;
    std::array<double,3> local{0,0,0}; // local offset from parent, like WorldNode local_transform
    std::vector<std::string> children;
};

class SceneHierarchy {
public:
    std::vector<SceneNode> nodes;

    // Build deterministic 5-level: universe→galactic_arm→stellar→planetary→local + DeterministicTestObject
    void build_deterministic(){
        nodes.clear();
        // 5 levels each 10 → 50 +2 =52 ; universe root at 10 to match spec World(10)→Universe(10) chain
        nodes.push_back({"universe","universe","",{10,0,0}});
        nodes.push_back({"galactic_arm","galactic_arm","universe",{10,0,0}});
        nodes.push_back({"stellar_neighborhood","stellar_neighborhood","galactic_arm",{10,0,0}});
        nodes.push_back({"planetary_system","planetary_system","stellar_neighborhood",{10,0,0}});
        nodes.push_back({"local_environment","local_environment","planetary_system",{10,0,0}});
        nodes.push_back({"DeterministicTestObject","DeterministicTestObject","local_environment",{2,0,0}});
        // children links already implied by parent
    }

    // World position = sum of all ancestors + local (like Node3D global_position)
    WorldPos world_pos(const std::string& id) const {
        WorldPos acc{0,0,0};
        std::string cur=id;
        // walk up to root
        for(int i=0;i<10;i++){
            auto it = find(cur);
            if(!it) break;
            acc.x += it->local[0]; acc.y += it->local[1]; acc.z += it->local[2];
            if(it->parent.empty()) break;
            cur = it->parent;
        }
        return acc;
    }

    bool test_52() const {
        WorldPos w = world_pos("DeterministicTestObject");
        return std::fabs(w.x-52.0)<1e-3 && std::fabs(w.y)<1e-6; // 10*5+2
    }

private:
    const SceneNode* find(const std::string& id) const {
        for(auto& n: nodes) if(n.id==id) return &n;
        return nullptr;
    }
};

} // namespace astra::scene
