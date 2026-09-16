#include "upscaling.h"
namespace astra::postprocess {
bool detect_fsr2_support(){ return false; } // scaffolding, hardware fallback
std::string fallback_note(){ return "FSR2 scaffolding: fallback to native 1920x1080, no temporal upscaling claimed"; }
bool is_scaffolding_only(){ return true; }
}
