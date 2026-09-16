#include <cmath>
// Relativity — Doppler g, beaming (p·u)^2, aberration, redshift 1+z, spectral blackbody shift
namespace astra::relativity {
inline float doppler_g(float v, float cos_theta){
    float gamma = 1.f/std::sqrt(1.f-v*v+1e-6f);
    return 1.f/(gamma*(1.f - v*cos_theta));
}
inline float beaming(float g){ return g*g*g; } // g^3
inline float redshift(float g){ return 1.f/g -1.f; } // 1+z
}
