#include "sonification.h"
namespace astra::audio::sonification {
AudioSourceDesc sonify_dataset(const std::string& obj, const std::string& ds, const Mapping& m, AudioTruth t){
 AudioSourceDesc d; d.id=obj+"_sonified"; d.truth=t; d.provenance.object_type=obj; d.provenance.dataset=ds; d.provenance.transformation=m.method; d.provenance.frequency_mapping=m.frequency_mapping; d.provenance.time_mapping=m.time_mapping; d.status=(t==AudioTruth::REAL_SIGNAL_SONIFICATION?ScientificStatus::OBSERVATIONAL:ScientificStatus::SIMULATED); d.provenance.source_class=truth_to_string(t); return d;
}
bool validate_morphology_preserved(const AudioSourceDesc& d){
 return d.provenance.frequency_mapping.find("log")!=std::string::npos || d.provenance.frequency_mapping.find("linear")!=std::string::npos;
}
}
