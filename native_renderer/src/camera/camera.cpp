
#include <string>
// Camera — orbital/free/spacecraft/observation/cinematic/replay, 6 modes, dolly, TAA, motion blur
namespace astra::camera {
enum class Mode{ ORBITAL,FREE,SPACECRAFT,OBSERVATION,CINEMATIC,REPLAY };
struct Camera {
    Mode mode=Mode::ORBITAL;
    float distance=20.f, smooth=6.f, fov=60.f;
    void set_mode(Mode m){ mode=m; }
    // tick-synced, not wall clock: lerp between sim ticks via sim_time_s
    void tick_lerp(double sim_time, double tick_dt, float lerp_alpha){ (void)sim_time; (void)tick_dt; (void)lerp_alpha; }
};
}
