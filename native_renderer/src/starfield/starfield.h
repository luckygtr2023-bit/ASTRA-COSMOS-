#pragma once
#include <cstdint>
#include <string>
namespace astra::starfield {
enum class StarLOD { POINT, BILLBOARD, IMPOSTOR, PROCEDURAL_SURFACE };
StarLOD lod_for_distance(double dist_m, double radius_m);
struct StarCatalogEntry { double ra, dec, distance_pc, magnitude, temp_k; std::string spectype; };
struct StarRendererConfig { uint64_t seed=0xA573; uint32_t capacity=10000000; bool indirect=true; bool gpu_culling=true; };
uint32_t streaming_budget(uint32_t vram);
}
