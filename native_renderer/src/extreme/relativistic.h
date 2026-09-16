#pragma once
#include <string>
namespace astra::relativity {
double doppler_g(double vel, double cos_theta); // 1/(gamma(1 - v cos))
double gravitational_redshift(double rs, double r); // sqrt(1 - rs/r)
double spacetime_curvature(double rs, double r);
struct TidalTensor { double xx, yy, zz; std::string label="THEORETICAL"; };
TidalTensor tidal_field(double rs, double r);
}
