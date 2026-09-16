#pragma once
#include <string>
namespace astra::cosmic {
struct FilamentParams { double density=1e-27; double length_mpc=50; std::string visualization="volumetric density field"; };
void generate_filament(FilamentParams p, double* density_field, int n);
struct VoidParams { double radius_mpc=20; };
}
