#pragma once
#include <string>
namespace astra::spacetime {
struct CurvatureField { double rs=0; double strength=1; std::string visualization="grid distortion"; };
void distort_grid(double* grid, int n, CurvatureField f);
}
