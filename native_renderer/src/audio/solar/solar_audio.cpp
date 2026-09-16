
#include "solar_audio.h"
namespace astra::audio::solar {
AudioSourceDesc solar_oscillations(double f, AudioQuality q){
 AudioSourceDesc d; d.id="sun_osc"; d.truth=AudioTruth::REAL_SIGNAL_SONIFICATION; d.status=ScientificStatus::OBSERVATIONAL;
 d.provenance.object_type="sun"; d.provenance.audio_type="acoustic_oscillation"; d.provenance.dataset="SOHO/GONG 5min oscillation 3000 microHz";
 d.provenance.transformation="freq shift microHz->Hz log mapping"; d.provenance.frequency_mapping="3000uHz->440Hz"; d.base_frequency_hz=float(f*0.146); d.quality=q; d.spatial=false; return d;
}
AudioSourceDesc solar_flare(const std::string& ds, AudioTruth t){
 AudioSourceDesc d; d.id="sun_flare"; d.truth=t; d.status=(t==AudioTruth::REAL_SIGNAL_SONIFICATION?ScientificStatus::OBSERVATIONAL:ScientificStatus::SIMULATED);
 d.provenance.object_type="sun"; d.provenance.audio_type="flare_radio"; d.provenance.dataset=ds; d.provenance.transformation="radio flux->AM"; return d;
}
AudioSourceDesc solar_wind(const std::string& sc, bool derived){
 AudioSourceDesc d; d.id="solar_wind"; d.truth=derived?AudioTruth::REAL_SIGNAL_SONIFICATION:AudioTruth::PHYSICALLY_MODELED; d.status=derived?ScientificStatus::OBSERVATIONAL:ScientificStatus::SIMULATED;
 d.provenance.object_type="sun"; d.provenance.audio_type="plasma_wave"; d.provenance.dataset=sc+" plasma wave"; return d;
}
}
