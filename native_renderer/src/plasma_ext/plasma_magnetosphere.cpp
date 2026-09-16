#include "plasma_magnetosphere.h"
#include <cmath>
namespace astra::plasma {
void emit_plasma(PlasmaParams p, double* o,int n){ for(int i=0;i<n;i++) o[i]= p.density * std::sin(i*0.1) * p.B_nT; }
void trace_field_line(MagnetosphereParams, double* l,int n){ for(int i=0;i<n;i++) l[i]= std::sin(i*0.1)*10; }
}
