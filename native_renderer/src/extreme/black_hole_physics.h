#pragma once
#include <string>
namespace astra::extreme {
// Schwarzschild metric + Kerr evaluation, ray integration, accretion physics
struct SchwarzschildParams { double mass_kg=1.989e31; double rs_m=29540; double spin_a=0; }; // 10M sun
struct KerrParams { double spin_a=0.9; double r_plus=0; };
struct AccretionParams {
    double r_in=3, r_out=8; // in rs
    double temperature_scale=1e4;
    double density=1.0;
    double thickness=0.1;
    bool turbulence=true;
    std::string scientific_status="THEORETICAL";
};
double photon_sphere(double rs){ return 1.5*rs; }
double shadow_radius(double rs){ return 2.6*rs; }
double isco(double rs, double spin){ (void)spin; return 3*rs; } // Schwarzschild 3rs, Kerr would be <3
double deflection_angle(double rs, double b){ return 2*rs/std::max(b,0.001); } // alpha=2rs/b
struct Ray { double t=0; double redshift_g=1.0; double lensing_alpha=0; };
Ray trace_ray_schwarzschild(const double* ro, const double* rd, double rs, int steps);
}
