
#pragma once
#include "../audio_types.h"
namespace astra::audio::pulsar {
AudioSourceDesc pulsar_timing(const std::string& name, double period_ms, const std::string& dataset, bool preserve_timing);
}
