
#include "pulsar_audio.h"
namespace astra::audio::pulsar {
AudioSourceDesc pulsar_timing(const std::string& n, double per, const std::string& ds, bool preserve){
 AudioSourceDesc d; d.id=n; d.truth=AudioTruth::REAL_SIGNAL_SONIFICATION; d.status=ScientificStatus::OBSERVATIONAL; d.provenance.object_type="pulsar"; d.provenance.audio_type="radio_timing"; d.provenance.dataset=ds; d.provenance.transformation=preserve?"preserve timing 1:1 "+std::to_string(per)+"ms":"time compressed"; d.base_frequency_hz=float(1000.0/per); d.quality=AudioQuality::SCIENTIFIC; return d;
}
}
