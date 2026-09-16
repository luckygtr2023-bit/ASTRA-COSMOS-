#pragma once
#include <string>
namespace astra::atmosphere {
struct AtmosphereParams {
    std::string composition = "Earth N2/O2 78/21";
    float rayleigh_beta = 4e-6f;
    float mie_beta = 2.1e-5f;
    float ozone_absorption = 0.001f;
    float planet_radius = 6371000.f;
    float atmo_radius = 6471000.f;
    float Rayleigh_scale = 8000.f;
    float Mie_scale = 1200.f;
    std::string scientific_status = "SIMULATED";
    static AtmosphereParams earth(){ return {};}
    static AtmosphereParams mars(){ AtmosphereParams p; p.composition="Mars CO2 95%"; p.rayleigh_beta=0.5e-6f; p.mie_beta=5e-6f; p.Rayleigh_scale=11000; return p;}
    static AtmosphereParams venus(){ AtmosphereParams p; p.composition="Venus CO2 96%"; p.rayleigh_beta=8e-6f; p.mie_beta=1e-4f; return p;}
};
}
