#pragma once
// ASTRA Phase01 — Coordinate Bridge + Hierarchical Frames
// Double precision simulation → float relative for GPU, origin rebasing, 5-level hierarchy
// Invariant: renderer never modifies scientific truth, only visual approximation

#include "floating_origin.h"
#include <string>
#include <unordered_map>
#include <vector>

namespace astra::scene {

// Hierarchical frame — universe → galactic_arm → stellar → planetary → local
struct FrameTransform {
    std::string id;
    std::string parent;
    std::array<double,3> local{0,0,0};
};

class CoordinateBridge {
public:
    void set_origin(const WorldPos& origin) { rebaser_.current_origin = origin; }
    WorldPos origin() const { return rebaser_.current_origin; }

    // World (double) → relative (float) for GPU, stable at 5,0,0 even at 1e26
    static std::array<float,3> world_to_relative(const WorldPos& world, const WorldPos& origin) {
        return OriginRebaser::world_to_relative(world, origin);
    }

    // Hierarchical world pos sum (like Node3D global_position)
    WorldPos hierarchical_world_pos(const std::string& id) const;

    // Frame graph: register transforms
    void register_frame(const FrameTransform& f) { frames_[f.id]=f; }
    void clear() { frames_.clear(); }

    // Precision diagnostics — how much double→float error at scale?
    struct PrecisionReport { double world_scale; float error; bool stable; };
    PrecisionReport diagnose_precision(double scale) const;

    // Floating-origin hook called every tick
    struct RebaseEvent { WorldPos old_origin, new_origin; };
    RebaseEvent rebase(const WorldPos& new_origin) {
        auto r = rebaser_.request_and_execute(new_origin);
        return {r.old_origin, r.new_origin};
    }

    OriginRebaser& rebaser() { return rebaser_; }

private:
    OriginRebaser rebaser_;
    std::unordered_map<std::string, FrameTransform> frames_;
};

} // namespace astra::scene
