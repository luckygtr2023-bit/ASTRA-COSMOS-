#include <vector>
#include <string>
// Stellar Renderer — 10k→20k stars instanced, spectral OBAFGKM → blackbody LUT 16×256
namespace astra::stellar {
struct Star { double x,y,z; float temp_k; float lum; };
std::vector<Star> generate_10k(){
    std::vector<Star> out; out.reserve(10000);
    for(int i=0;i<10000;i++){
        float t = 3000.f + (float)(i%16)/16.f*37000.f; // 16 temp buckets
        out.push_back({(i%100)*10.0,0,(i/100)*10.0, t,1.0});
    }
    return out;
}
// GPU would sample star_temperature_lut.ppm via sampler2D
}
