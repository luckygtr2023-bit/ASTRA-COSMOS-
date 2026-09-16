#pragma once
#include <string>
#include <cstdint>
namespace astra::vfx {
// Astrophysical VFX — each connected to scientific params, not arbitrary random
struct SolarFlareParams { double energy_J=1e25; double temp_K=1e7; double density=1e-6; double B_nT=10; double velocity=5e5; };
struct CMEParams { double mass_kg=1e12; double velocity=1e6; double energy=1e23; };
struct AuroraParams { double magnetic_field=50e-6; double solar_wind_pressure=2e-9; };
struct JetParamsExt { double luminosity=1e38; double velocity_c=0.9; double temp_K=1e9; };
struct NebulaVFXParams { double density=1e-18; double temp_K=1e4; double composition=0.5; };
struct GWParams { double strain=1e-21; double frequency=100; };
struct VFXTrigger { std::string id; std::string classification="REAL"; double time_s=0; };
std::string flare_emissive(const SolarFlareParams& p); // temp->color
std::string cme_visual(const CMEParams& p);
std::string aurora_visual(const AuroraParams& p);
std::string jet_visual(const JetParamsExt& p);
bool is_param_driven(const std::string& effect); // true if scientific param available
}
