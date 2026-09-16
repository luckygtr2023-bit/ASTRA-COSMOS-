
#include "planetary_audio.h"
namespace astra::audio::planetary {
AudioSourceDesc earth_atmosphere(AudioQuality q){ AudioSourceDesc d; d.id="earth_atmo"; d.truth=AudioTruth::REAL_ACOUSTIC; d.status=ScientificStatus::OBSERVATIONAL; d.provenance.object_type="earth"; d.provenance.audio_type="atmosphere"; d.provenance.dataset="Earth atmosphere wind/thunder/ocean seismic"; d.quality=q; return d; }
AudioSourceDesc mars_wind(bool derived){ AudioSourceDesc d; d.id="mars_wind"; d.truth=derived?AudioTruth::REAL_SIGNAL_SONIFICATION:AudioTruth::PHYSICALLY_MODELED; d.status=derived?ScientificStatus::OBSERVATIONAL:ScientificStatus::SIMULATED; d.provenance.object_type="mars"; d.provenance.audio_type="thin_atmosphere_wind"; d.provenance.dataset=derived?"Mars InSight pressure sonified":"modeled dust turbulence"; return d; }
AudioSourceDesc jupiter_radio(AudioTruth t){ AudioSourceDesc d; d.id="jupiter_radio"; d.truth=t; d.status=ScientificStatus::OBSERVATIONAL; d.provenance.object_type="jupiter"; d.provenance.audio_type="magnetosphere_radio"; d.provenance.dataset="Juno/Waves radio"; return d; }
AudioSourceDesc generic_planet(const std::string& p, AudioTruth t){ AudioSourceDesc d; d.id=p+"_generic"; d.truth=t; d.status=ScientificStatus::SIMULATED; d.provenance.object_type=p; d.provenance.audio_type="magnetosphere"; return d; }
}
