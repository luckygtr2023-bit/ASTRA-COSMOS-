#include "relativistic.h"
#include <cmath>
namespace astra::relativity {
double doppler_g(double v, double c){ double gamma=1/std::sqrt(1-v*v); return 1/(gamma*(1 - v*c)); }
double gravitational_redshift(double rs, double r){ if(r<=rs) return 0; return std::sqrt(1 - rs/r); }
double spacetime_curvature(double rs, double r){ return rs/(r*r); }
TidalTensor tidal_field(double rs, double r){ double t = 2*rs/(r*r*r); return {t, -t/2, -t/2, "THEORETICAL"}; }
}
