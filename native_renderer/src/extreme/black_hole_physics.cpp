#include "black_hole_physics.h"
#include <cmath>
namespace astra::extreme {
Ray trace_ray_schwarzschild(const double* ro, const double* rd, double rs, int steps){
    Ray r; r.t= steps*0.01; r.lensing_alpha = 2*rs/1.0; r.redshift_g=1.0; (void)ro;(void)rd; return r;
}
}
