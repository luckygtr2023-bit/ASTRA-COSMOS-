
#pragma once
#include "../audio_types.h"
namespace astra::audio::black_hole {
enum class Mode { OBSERVATIONAL, ACCRETION_MEDIUM, GW_SONIFICATION, RELATIVISTIC_MODELED, CINEMATIC };
AudioSourceDesc bh_mode(Mode m, const std::string& dataset, AudioTruth truth);
AudioSourceDesc bh_merger_gw(const std::string& event, double chirp_mass, bool data_derived);
}
