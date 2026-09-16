
#include "galaxy_audio.h"
namespace astra::audio::galaxy {
AudioSourceDesc galaxy_sonify(const std::string& gid, double sfr, double rot, const std::string& ds){
 AudioSourceDesc d; d.id=gid; d.truth=AudioTruth::SCIENTIFICALLY_INTERPRETED; d.status=ScientificStatus::SIMULATED; d.provenance.object_type="galaxy"; d.provenance.audio_type="galaxy_params"; d.provenance.dataset=ds; d.provenance.transformation="SFR "+std::to_string(sfr)+" rot "+std::to_string(rot)+" -> pitch/amplitude deterministic 0xA573"; d.base_frequency_hz=float(110+rot); return d;
}
AudioSourceDesc cluster_sonify(const std::string& cid, double temp){
 AudioSourceDesc d; d.id=cid; d.truth=AudioTruth::SCIENTIFICALLY_INTERPRETED; d.status=ScientificStatus::SIMULATED; d.provenance.object_type="cluster"; d.provenance.audio_type="icm_xray"; d.provenance.dataset="ICM temp "+std::to_string(temp)+"keV"; return d;
}
}
