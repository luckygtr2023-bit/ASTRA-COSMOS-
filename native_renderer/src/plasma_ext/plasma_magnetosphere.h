#pragma once
#include <string>
namespace astra::plasma {
struct PlasmaParams { double density=1e6, temp_eV=100, B_nT=10; std::string status="SIMULATED"; };
struct MagnetosphereParams { double standoff_m= 6371000*10; std::string status="SIMULATED"; };
struct JetParams { double vel_c=0.9, doppler_g=2.0; std::string status="THEORETICAL"; };
void emit_plasma(PlasmaParams p, double* out, int n);
void trace_field_line(MagnetosphereParams m, double* line, int n);
}
