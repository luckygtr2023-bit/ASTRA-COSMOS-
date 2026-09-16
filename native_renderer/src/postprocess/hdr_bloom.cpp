#include "hdr_bloom.h"
#include <cmath>
namespace astra::postprocess {
float luminance_extract(float r,float g,float b){ return 0.2126f*r+0.7152f*g+0.0722f*b; }
float exposure_for_bright(float e){ return 1.0f / (1.0f + e*0.1f); }
bool bloom_not_destroy(){ return true; }
}
