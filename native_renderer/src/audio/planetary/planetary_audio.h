
#pragma once
#include "../audio_types.h"
namespace astra::audio::planetary {
AudioSourceDesc earth_atmosphere(AudioQuality q);
AudioSourceDesc mars_wind(bool data_derived);
AudioSourceDesc jupiter_radio(AudioTruth t);
AudioSourceDesc generic_planet(const std::string& planet, AudioTruth t);
}
