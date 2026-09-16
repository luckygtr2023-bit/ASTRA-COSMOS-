#include "visualization_modes.h"
namespace astra::visualization {
std::string mode_label(SciVisMode m){
    if(m==SciVisMode::REAL) return "REAL";
    if(m==SciVisMode::THEORETICAL) return "THEORETICAL";
    if(m==SciVisMode::SPECULATIVE) return "SPECULATIVE";
    return "CINEMATIC";
}
std::string mode_watermark(SciVisMode m){
    if(m==SciVisMode::SPECULATIVE) return "SPECULATIVE watermark 0.2";
    if(m==SciVisMode::THEORETICAL) return "THEORETICAL watermark 0.1";
    return "none";
}
bool never_disguise_speculation(SciVisMode m){ (void)m; return true; }
std::string example_for_mode(SciVisMode m){
    if(m==SciVisMode::REAL) return "Real astronomical observation";
    if(m==SciVisMode::THEORETICAL) return "Theoretical wormhole visualization";
    if(m==SciVisMode::SPECULATIVE) return "Speculative warp visualization";
    return "Cinematic presentation";
}
}
