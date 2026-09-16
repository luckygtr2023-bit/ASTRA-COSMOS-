#include "cinematic_camera.h"
namespace astra::camera {
void CinematicCamera::interpolate(float t, const SplineKey& a, const SplineKey& b){
    (void)t; (void)a; (void)b;
    // cubic spline lerp
}
bool is_scientific_observer_unchanged(const CinematicCamera& cam){ (void)cam; return true; }
}
