#pragma once
#include "floating_origin.h"
#include <string>
#include <vector>
#include <unordered_map>

namespace astra::scene {

// RenderState — mirrors bridge_state.json, consumed by renderer, never authority
struct ObjectState {
    std::string id;
    std::string kind; // STAR, PLANET, BLACK_HOLE, etc.
    WorldPos pos; // double authoritative
    std::string frame = "world";
    std::string classification = "SIMULATED_DATA"; // REAL/THEO/SPEC
    int lod = 0;
    float mass_kg = 0;
    float rs = 0.f; // Schwarzschild radius render units
};

struct RenderState {
    uint64_t tick = 42;
    double sim_time_s = 1234.5;
    std::string frame_id = "world";
    WorldPos origin_offset{0,0,0};
    std::vector<ObjectState> objects;
    struct Camera { std::string mode="orbital"; std::string target="planet-1"; } camera;
    std::string quality = "HIGH";
};

class Scene {
public:
    RenderState state;
    OriginRebaser rebaser;
    SceneHierarchy hierarchy;

    void load_bridge_json(const std::string& path); // reads bridge_state.json hash compare
    void update_from_render_state(const RenderState& s){
        state = s;
        rebaser.current_origin = s.origin_offset;
    }
    // Relative positions for GPU (float)
    std::vector<std::array<float,3>> gpu_positions() const {
        std::vector<std::array<float,3>> out;
        for(auto& o: state.objects){
            out.push_back(OriginRebaser::world_to_relative(o.pos, rebaser.current_origin));
        }
        return out;
    }
};

} // namespace astra::scene
