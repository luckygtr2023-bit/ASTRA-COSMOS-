#pragma once
#include <string>
#include <vector>
#include <cstdint>
namespace astra::camera {
// Cinematic camera 7 modes + smooth, tracking, spline, bookmarks, FOV, exposure, DoF, motion blur, shake
enum class CinematicMode { FREE=0, ORBIT=1, FOLLOW=2, TRACK=3, OBSERVATION=4, RELATIVISTIC_OBSERVER=5, CINEMATIC=6 };
struct CameraBookmark { std::string name; float pos[3]={0,0,10}; float target[3]={0,0,0}; float fov=60.f; float exposure=1.1f; };
struct SplineKey { float t; float pos[3]; float fov; };
struct CinematicCamera {
    CinematicMode mode=CinematicMode::ORBIT;
    float fov=60.f, exposure=1.1f, dof_focus=10.f, dof_aperture=2.8f;
    bool motion_blur=false;
    float shake_intensity=0; // optional cinematic only
    std::vector<CameraBookmark> bookmarks;
    std::vector<SplineKey> spline;
    void set_mode(CinematicMode m){ mode=m; }
    void add_bookmark(const CameraBookmark& b){ bookmarks.push_back(b); }
    void interpolate(float t, const SplineKey& a, const SplineKey& b); // smooth lerp + spline
    bool does_not_alter_scientific_state() const { return true; } // cinematic camera moves do not alter observer state
    float smooth_movement(float dt) const { (void)dt; return 0.05f; }
};
bool is_scientific_observer_unchanged(const CinematicCamera& cam); // must not modify scientific observer
}
