
#pragma once
#include "../audio_types.h"
#include "../../scene/floating_origin.h"
namespace astra::audio::spatial {
struct Listener { scene::WorldPos pos{0,0,0}; scene::WorldPos vel{0,0,0}; float yaw=0; };
float distance_attenuation(const scene::WorldPos& src, const Listener& lst, bool in_atmosphere);
float doppler_shift(float base_freq, const scene::WorldPos& src_vel, const Listener& lst);
float occlusion(const scene::WorldPos& src, const scene::WorldPos& lst);
}
