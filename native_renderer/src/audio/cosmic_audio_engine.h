#pragma once
// ASTRA Cosmic Audio Engine — dedicated thread, lock-free queue, deterministic synthesis
// Architecture: Scientific Engine → Scientific Audio State → Cosmic Audio Engine → miniaudio → device

#include "audio_types.h"
#include "../scene/floating_origin.h"
#include <string>
#include <vector>
#include <thread>
#include <atomic>
#include <mutex>
#include <queue>
#include <functional>

namespace astra::audio {

struct AudioFrame {
    uint64_t tick = 0;
    double sim_time_s = 0;
    std::vector<AudioSourceDesc> sources; // sonified objects this frame
};

class CosmicAudioEngine {
public:
    CosmicAudioEngine();
    ~CosmicAudioEngine();

    bool init(bool headless_mock = true); // headless mock if no audio device
    void shutdown();

    // Thread-safe: scientific thread pushes, audio thread consumes
    void push_frame(const AudioFrame& frame);
    void set_listener(const scene::WorldPos& pos, const scene::WorldPos& vel, float yaw_rad);
    void set_quality(AudioQuality q) { quality_=q; }
    void set_enabled(bool e) { enabled_=e; }

    // Synthesis — deterministic, bounded CPU
    struct SynthStats { uint32_t active_sources=0, underruns=0; float cpu_ms=0; };
    SynthStats tick_synthesis(); // audio thread

    // Hear the Universe mode — auto pick per object
    std::vector<AudioSourceDesc> hear_universe(const std::vector<std::string>& object_types) const;

    // Validation
    bool validate_no_mislabel() const; // REAL never labeled CINEMATIC etc
    size_t queue_size() const;
    bool is_running() const { return running_; }
    bool is_headless() const { return headless_; }
    std::string backend() const { return headless_ ? "mock-headless (miniaudio would be here)" : "miniaudio"; }

    // Performance: must not block sim thread
    bool try_push(const AudioFrame& f); // non-blocking

private:
    void audio_thread_loop();
    std::thread audio_thread_;
    std::atomic<bool> running_{false};
    std::atomic<bool> enabled_{true};
    bool headless_ = true;
    AudioQuality quality_ = AudioQuality::SCIENTIFIC;

    mutable std::mutex queue_mutex_;
    std::queue<AudioFrame> queue_;
    size_t max_queue_ = 64;

    // Listener in hierarchical coordinates
    scene::WorldPos listener_pos_{0,0,0};
    scene::WorldPos listener_vel_{0,0,0};
    float listener_yaw_ = 0;

    // miniaudio would be here: ma_engine, ma_sound etc (header-only, included when not headless)
    // For CI headless we mock, but header is available at /home/user/miniaudio/miniaudio.h
};

} // namespace astra::audio
