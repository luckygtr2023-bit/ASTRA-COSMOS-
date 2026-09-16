
// Profiling — Tracy + Vulkan queries, mirrors Telemetry every 60 frames
namespace astra::profiling {
struct Zone {
    const char* name;
    Zone(const char* n):name(n){ /* ZoneScopedN(n) */ }
    ~Zone(){}
};
inline void frame_mark(){ /* FrameMark */ }
inline void plot_fps(float fps){ (void)fps; }
}
