#include "cosmic_structure.h"
#include <cmath>
namespace astra::cosmic {
void generate_filament(FilamentParams p, double* f,int n){ for(int i=0;i<n;i++) f[i]= p.density * (1+0.5*std::sin(i*0.1))* (1 - double(i)/n*0.5); }
}
