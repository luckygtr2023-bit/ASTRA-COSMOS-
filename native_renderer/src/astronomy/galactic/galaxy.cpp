#include <vector>
#include <cmath>
// Galactic — logarithmic spiral density wave, 2 arms, b=0.22
namespace astra::galactic {
struct StarPos{ float x,z; };
std::vector<StarPos> spiral(int count=500, float b=0.22f, int arms=2){
    std::vector<StarPos> out; out.reserve(count);
    for(int i=0;i<count;i++){
        float r = 5.f + (float)i/count*30.f;
        float theta = std::log(r/5.f)/b + (i%arms)*3.14159f*2.f/arms;
        out.push_back({r*cos(theta), r*sin(theta)});
    }
    return out;
}
}
