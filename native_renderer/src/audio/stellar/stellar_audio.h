
#pragma once
#include "../audio_types.h"
namespace astra::audio::stellar {
AudioSourceDesc stellar_oscillation(const std::string& star, double period_days, const std::string& dataset);
AudioSourceDesc variable_star(const std::string& var_id, const std::string& light_curve_dataset);
}
