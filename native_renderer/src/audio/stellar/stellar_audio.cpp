
#include "stellar_audio.h"
namespace astra::audio::stellar {
AudioSourceDesc stellar_oscillation(const std::string& star, double p, const std::string& ds){ AudioSourceDesc d; d.id=star+"_osc"; d.truth=AudioTruth::REAL_SIGNAL_SONIFICATION; d.status=ScientificStatus::OBSERVATIONAL; d.provenance.object_type="star"; d.provenance.audio_type="stellar_oscillation"; d.provenance.dataset=ds; d.provenance.transformation="period "+std::to_string(p)+"d -> audible"; d.base_frequency_hz=float(440.0/p); return d; }
AudioSourceDesc variable_star(const std::string& vid, const std::string& ds){ AudioSourceDesc d; d.id=vid; d.truth=AudioTruth::DATA_DERIVED; d.status=ScientificStatus::OBSERVATIONAL; d.provenance.object_type="variable_star"; d.provenance.audio_type="light_curve"; d.provenance.dataset=ds; d.provenance.frequency_mapping="mag->pitch log"; return d; }
}
