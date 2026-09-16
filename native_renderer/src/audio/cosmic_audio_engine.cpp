#include "cosmic_audio_engine.h"
#include <cstdio>
#include <algorithm>
#include <chrono>

namespace astra::audio {

std::string Provenance::to_json() const {
    return "{\"object_id\":\""+object_id+"\",\"object_type\":\""+object_type+"\",\"audio_type\":\""+audio_type+"\",\"source_class\":\""+source_class+"\",\"dataset\":\""+dataset+"\",\"transformation\":\""+transformation+"\",\"frequency_mapping\":\""+frequency_mapping+"\",\"scientific_status\":\""+status_to_string(scientific_status)+"\"}";
}

CosmicAudioEngine::CosmicAudioEngine(){}
CosmicAudioEngine::~CosmicAudioEngine(){ shutdown(); }

bool CosmicAudioEngine::init(bool headless_mock){
    if(running_) return true;
    headless_ = headless_mock;
#if __has_include("/home/user/miniaudio/miniaudio.h")
    // Real miniaudio would init ma_engine here
    if(!headless_){
        std::printf("[CosmicAudio] miniaudio init (would be ma_engine_init)\n");
    } else {
        std::printf("[CosmicAudio] headless mock — miniaudio header at /home/user/miniaudio/miniaudio.h (deterministic synthesis, no device)\n");
    }
#else
    std::printf("[CosmicAudio] miniaudio header not found — mock synthesis\n");
    headless_ = true;
#endif
    running_ = true;
    // audio_thread_ = std::thread(&CosmicAudioEngine::audio_thread_loop, this);
    std::printf("[CosmicAudio] init headless=%d quality=SCIENTIFIC thread=dedicated (mock loop)\n", headless_);
    return true;
}
void CosmicAudioEngine::shutdown(){
    if(!running_) return;
    running_ = false;
    if(audio_thread_.joinable()) audio_thread_.join();
    std::printf("[CosmicAudio] shutdown complete — no sim thread block\n");
}
void CosmicAudioEngine::push_frame(const AudioFrame& frame){
    std::lock_guard<std::mutex> lk(queue_mutex_);
    if(queue_.size() >= max_queue_){
        queue_.pop(); // drop oldest (bounded)
    }
    queue_.push(frame);
}
bool CosmicAudioEngine::try_push(const AudioFrame& f){
    std::lock_guard<std::mutex> lk(queue_mutex_);
    if(queue_.size() >= max_queue_) return false;
    queue_.push(f);
    return true;
}
void CosmicAudioEngine::set_listener(const scene::WorldPos& pos, const scene::WorldPos& vel, float yaw){
    listener_pos_=pos; listener_vel_=vel; listener_yaw_=yaw;
}
CosmicAudioEngine::SynthStats CosmicAudioEngine::tick_synthesis(){
    SynthStats s;
    std::lock_guard<std::mutex> lk(queue_mutex_);
    if(!queue_.empty()){
        auto& f = queue_.front();
        s.active_sources = (uint32_t)f.sources.size();
        // Deterministic synthesis bounded CPU: would generate sine per source frequency_mapping
        queue_.pop();
    }
    s.cpu_ms = 0.2f; // mock bounded
    return s;
}
std::vector<AudioSourceDesc> CosmicAudioEngine::hear_universe(const std::vector<std::string>& types) const {
    std::vector<AudioSourceDesc> out;
    for(auto& t: types){
        AudioSourceDesc d;
        d.id = "hear_"+t;
        d.provenance.object_type = t;
        if(t=="earth"||t=="moon"||t=="mars_atmosphere"){
            d.truth=AudioTruth::REAL_ACOUSTIC; d.status=ScientificStatus::SIMULATED; d.provenance.dataset="modeled atmospheric wind 0.1Hz";
        } else if(t=="pulsar"||t=="gravitational_wave"){
            d.truth=AudioTruth::REAL_SIGNAL_SONIFICATION; d.status=ScientificStatus::OBSERVATIONAL; d.provenance.dataset="public dataset sonified";
        } else if(t=="black_hole"||t=="accretion"){
            d.truth=AudioTruth::PHYSICALLY_MODELED; d.status=ScientificStatus::SIMULATED; d.provenance.dataset="T~r^-3/4 modeled";
        } else if(t=="wormhole"){
            d.truth=AudioTruth::SPECULATIVE; d.status=ScientificStatus::SPECULATIVE; d.provenance.dataset="Morris-Thorne b(r)";
        } else {
            d.truth=AudioTruth::CINEMATIC; d.status=ScientificStatus::CINEMATIC; d.provenance.dataset="cinematic ambience";
        }
        d.provenance.source_class = truth_to_string(d.truth);
        d.provenance.scientific_status = d.status;
        out.push_back(d);
    }
    return out;
}
bool CosmicAudioEngine::validate_no_mislabel() const {
    std::lock_guard<std::mutex> lk(queue_mutex_);
    std::queue<AudioFrame> copy = queue_;
    while(!copy.empty()){
        for(auto& s: copy.front().sources){
            if(!validate_label(s.truth, s.status)) return false;
            // REAL never labeled CINEMATIC
            if(s.truth==AudioTruth::REAL_ACOUSTIC && s.status==ScientificStatus::CINEMATIC) return false;
            if(s.truth==AudioTruth::REAL_SIGNAL_SONIFICATION && s.status==ScientificStatus::SPECULATIVE) return false;
        }
        copy.pop();
    }
    return true;
}
size_t CosmicAudioEngine::queue_size() const { std::lock_guard<std::mutex> lk(queue_mutex_); return queue_.size(); }
void CosmicAudioEngine::audio_thread_loop(){
    while(running_){
        tick_synthesis();
        std::this_thread::sleep_for(std::chrono::milliseconds(5)); // ~200Hz
    }
}

} // namespace astra::audio
