#pragma once
// ASTRA Cosmic Audio Engine — Truth Model + Classification (F-Z)
// Distinguishes observation vs sonification vs modeled vs cinematic

#include <string>
#include <vector>
#include <cstdint>

namespace astra::audio {

// Audio truth classification — every source must have one
enum class AudioTruth {
    REAL_ACOUSTIC,               // Earth atmosphere, spacecraft interior
    REAL_SIGNAL_SONIFICATION,    // pulsar radio, GW waveform shifted audible
    DATA_DERIVED,                // generic data-derived sonification
    PHYSICALLY_MODELED,          // accretion disk plasma waves modeled
    SCIENTIFICALLY_INTERPRETED,  // scientific mapping of quantities
    CINEMATIC,                   // creative sound design
    SPECULATIVE                  // theoretical/wormhole/warp
};

enum class ScientificStatus {
    OBSERVATIONAL,   // real dataset
    SIMULATED,       // modeled with physics
    THEORETICAL,     // derived theory
    SPECULATIVE,     // conceptual
    CINEMATIC        // not scientific
};

enum class AudioQuality {
    SCIENTIFIC,   // minimum art processing
    REALISTIC,    // physically motivated
    CINEMATIC,    // creative allowed
    IMMERSIVE,    // gameplay optimized
    SPECULATIVE   // theoretical
};

struct Provenance {
    std::string object_id;
    std::string object_type; // planet, star, black_hole, pulsar, galaxy, etc
    std::string audio_type; // e.g., "gravitational_wave", "radio_sonification"
    std::string source_class; // AudioTruth string
    std::string dataset; // e.g., "GW150914 Hanford"
    std::string source_reference; // DOI / URL / mission
    std::string transformation; // e.g., "frequency shift 60Hz->440Hz linear"
    std::string frequency_mapping; // e.g., "log 10Hz->1000Hz"
    std::string time_mapping; // e.g., "1s GW -> 2s audio 2x stretch"
    ScientificStatus scientific_status = ScientificStatus::SIMULATED;
    std::string license = "CC0";
    std::string version = "1.0";
    bool deterministic = true;
    uint32_t seed = 0xA573;

    std::string to_json() const;
    bool is_real_observation() const { return scientific_status==ScientificStatus::OBSERVATIONAL; }
};

inline std::string truth_to_string(AudioTruth t){
    switch(t){
        case AudioTruth::REAL_ACOUSTIC: return "REAL_ACOUSTIC";
        case AudioTruth::REAL_SIGNAL_SONIFICATION: return "REAL_SIGNAL_SONIFICATION";
        case AudioTruth::DATA_DERIVED: return "DATA_DERIVED";
        case AudioTruth::PHYSICALLY_MODELED: return "PHYSICALLY_MODELED";
        case AudioTruth::SCIENTIFICALLY_INTERPRETED: return "SCIENTIFICALLY_INTERPRETED";
        case AudioTruth::CINEMATIC: return "CINEMATIC";
        case AudioTruth::SPECULATIVE: return "SPECULATIVE";
    }
    return "UNKNOWN";
}
inline std::string status_to_string(ScientificStatus s){
    switch(s){
        case ScientificStatus::OBSERVATIONAL: return "OBSERVATIONAL";
        case ScientificStatus::SIMULATED: return "SIMULATED";
        case ScientificStatus::THEORETICAL: return "THEORETICAL";
        case ScientificStatus::SPECULATIVE: return "SPECULATIVE";
        case ScientificStatus::CINEMATIC: return "CINEMATIC";
    }
    return "UNKNOWN";
}
// Validation: never mislabel
inline bool validate_label(AudioTruth truth, ScientificStatus status){
    if(truth==AudioTruth::REAL_ACOUSTIC && status!=ScientificStatus::OBSERVATIONAL && status!=ScientificStatus::SIMULATED) return false;
    if(truth==AudioTruth::CINEMATIC && status!=ScientificStatus::CINEMATIC) return false;
    if(truth==AudioTruth::SPECULATIVE && status!=ScientificStatus::SPECULATIVE) return false;
    // REAL_SIGNAL_SONIFICATION must be OBSERVATIONAL or SIMULATED, not SPECULATIVE
    if(truth==AudioTruth::REAL_SIGNAL_SONIFICATION && status==ScientificStatus::SPECULATIVE) return false;
    return true;
}

struct AudioSourceDesc {
    std::string id;
    AudioTruth truth = AudioTruth::SCIENTIFICALLY_INTERPRETED;
    ScientificStatus status = ScientificStatus::SIMULATED;
    Provenance provenance;
    float base_frequency_hz = 440.f;
    float amplitude = 0.5f;
    bool spatial = true;
    AudioQuality quality = AudioQuality::SCIENTIFIC;
};

} // namespace astra::audio
