
#pragma once
#include "../audio_types.h"
namespace astra::audio::galaxy {
AudioSourceDesc galaxy_sonify(const std::string& galaxy_id, double sfr, double rotation_kms, const std::string& spectra_dataset);
AudioSourceDesc cluster_sonify(const std::string& cluster_id, double temp_keV);
}
