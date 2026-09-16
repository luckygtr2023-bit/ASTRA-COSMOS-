#pragma once
#include "../audio_types.h"
namespace astra::audio::sonification {
struct Mapping { std::string data_type; std::string frequency_mapping; std::string time_mapping; std::string method; };
AudioSourceDesc sonify_dataset(const std::string& object, const std::string& dataset, const Mapping& m, AudioTruth truth);
bool validate_morphology_preserved(const AudioSourceDesc& d);
}
