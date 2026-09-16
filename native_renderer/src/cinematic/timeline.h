#pragma once
#include <string>
#include <vector>
#include <cstdint>
namespace astra::cinematic {
enum class TrackType { CAMERA_POS, FOCUS, VFX_TRIGGER, EXPOSURE, FOV, TIME_SCALE, AUDIO_CUE, QUALITY };
struct Keyframe {
    double time_s=0;
    TrackType type=TrackType::CAMERA_POS;
    std::string value; // e.g., "focus Sun" or "flare VFX"
    uint64_t hash=0; // deterministic
};
struct Timeline {
    std::vector<Keyframe> keys;
    bool deterministic=true;
    uint64_t seed=0xA573;
    void add(const Keyframe& k){ keys.push_back(k); }
    std::string at_time(double t) const; // returns active value deterministic
    bool is_deterministic() const { return deterministic; }
    size_t count() const { return keys.size(); }
};
std::string example_timeline(); // T0 camera pos ... T5 return to observer
}
