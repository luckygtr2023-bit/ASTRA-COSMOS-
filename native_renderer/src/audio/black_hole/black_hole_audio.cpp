
#include "black_hole_audio.h"
namespace astra::audio::black_hole {
AudioSourceDesc bh_mode(Mode m, const std::string& ds, AudioTruth t){
 AudioSourceDesc d; d.id="bh_mode_"+std::to_string(int(m)); d.truth=t; d.provenance.dataset=ds;
 if(m==Mode::OBSERVATIONAL){ d.status=ScientificStatus::OBSERVATIONAL; d.provenance.audio_type="observational"; }
 else if(m==Mode::ACCRETION_MEDIUM){ d.status=ScientificStatus::SIMULATED; d.provenance.audio_type="accretion_plasma_wave"; }
 else if(m==Mode::GW_SONIFICATION){ d.truth=AudioTruth::REAL_SIGNAL_SONIFICATION; d.status=ScientificStatus::OBSERVATIONAL; d.provenance.audio_type="gravitational_wave"; }
 else if(m==Mode::RELATIVISTIC_MODELED){ d.status=ScientificStatus::THEORETICAL; d.provenance.audio_type="relativistic_modeled"; }
 else { d.truth=AudioTruth::CINEMATIC; d.status=ScientificStatus::CINEMATIC; d.provenance.audio_type="cinematic_rumble"; }
 d.provenance.object_type="black_hole"; return d;
}
AudioSourceDesc bh_merger_gw(const std::string& ev, double chirp, bool derived){
 AudioSourceDesc d; d.id=ev; d.truth=AudioTruth::REAL_SIGNAL_SONIFICATION; d.status=derived?ScientificStatus::OBSERVATIONAL:ScientificStatus::SIMULATED; d.provenance.object_type="black_hole_merger"; d.provenance.audio_type="gravitational_wave"; d.provenance.dataset=derived?ev+" LIGO":"sim chirp "+std::to_string(chirp); d.provenance.transformation="freq shift Hz->Audible log"; return d;
}
}
