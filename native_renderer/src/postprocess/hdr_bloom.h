#include <string>
#pragma once
#include <cstdint>
namespace astra::postprocess {
struct HDRConfig {
    bool hdr=true;
    float exposure=1.1f;
    float bloom_strength=0.35f;
    bool eye_adaptation=false;
    float luminance_min=0.01f, luminance_max=10.f;
    std::string tonemap="AgX"; // or ACES, Reinhard
};
float luminance_extract(float r,float g,float b); // 0.2126R+0.7152G+0.0722B
float exposure_for_bright(float emissive); // ensures stars/accretion/jets do not destroy image
bool bloom_not_destroy(); // bloom 0.35 prevents uncontrolled brightness
}
