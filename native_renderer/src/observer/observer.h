#pragma once
#include "../scene/floating_origin.h"
#include "../audio/audio_types.h"
#include <string>
namespace astra::observer {
enum class Mode { FREE, PLANET_SURFACE, SPACECRAFT, ORBITAL, INTERPLANETARY, INTERSTELLAR, GALACTIC, COSMOLOGICAL };
struct ObserverState {
    scene::WorldPos pos{0,0,0};
    scene::WorldPos vel{0,0,0};
    float yaw=0, pitch=0;
    Mode mode=Mode::FREE;
    double sim_time_s=1234.5;
    uint64_t tick=42;
    std::string frame="world";
    audio::AudioQuality audio_quality=audio::AudioQuality::SCIENTIFIC;
};
bool is_scientific_frame_independent(const ObserverState& o);
}
