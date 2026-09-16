
#pragma once
#include "audio_types.h"
#include "../scene/floating_origin.h"
#include <vector>
namespace astra::audio {
struct ScientificAudioState {
 uint64_t tick=42;
 double sim_time_s=1234.5;
 scene::WorldPos listener_pos{0,0,0};
 std::vector<Provenance> active_provenances;
 std::string to_json() const;
};
}
