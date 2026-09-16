#include "spacetime_grid.h"
namespace astra::spacetime {
void distort_grid(double* g,int n,CurvatureField f){ for(int i=0;i<n;i++) g[i] += f.rs/(1+i*0.1)*f.strength; }
}
