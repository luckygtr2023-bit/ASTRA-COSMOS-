
#pragma once
#include "../audio_types.h"
namespace astra::audio::solar {
AudioSourceDesc solar_oscillations(double freq_microhz, AudioQuality q);
AudioSourceDesc solar_flare(const std::string& dataset, AudioTruth truth);
AudioSourceDesc solar_wind(const std::string& spacecraft, bool data_derived);
}
