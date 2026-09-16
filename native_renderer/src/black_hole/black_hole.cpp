
// Black Hole — photon sphere 1.5r_s shadow 2.6r_s, raymarch 256 steps, accretion T∝r-3/4, watermark SPECULATIVE
#include <cmath>
namespace astra::bh {
constexpr float photon_sphere(float rs){ return 1.5f*rs; }
constexpr float shadow_radius(float rs){ return 2.6f*rs; }
inline float deflection_alpha(float rs, float b){ return 2.f*rs/std::max(b,1e-3f); } // α≈2r_s/b
inline float disk_temp(float r, float r_out){ return std::pow(r_out/r,0.75f)*1e4f; }
}
// ISCO 3r_s, Novikov-Thorne, g^3 beaming handled in shader
