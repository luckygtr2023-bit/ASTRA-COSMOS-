
#include "audio_state.h"
namespace astra::audio {
std::string ScientificAudioState::to_json() const { return "{\"tick\":"+std::to_string(tick)+",\"sim_time\":"+std::to_string(sim_time_s)+"}"; }
}
