#pragma once
#include <string>
namespace astra::postprocess {
enum class Upscaler { NONE, FSR2, DYNAMIC_RESOLUTION };
struct UpscaleConfig {
    Upscaler mode=Upscaler::FSR2;
    bool supported=false; // detect
    float render_scale=0.77f; // 1440p -> 4K
    bool fallback=true;
};
bool detect_fsr2_support();
std::string fallback_note();
bool is_scaffolding_only(); // do not claim implementation if only scaffolding
}
