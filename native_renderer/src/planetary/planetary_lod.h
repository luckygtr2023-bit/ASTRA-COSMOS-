#pragma once
#include <cstdint>
#include <vector>
#include <string>
#include "../scene/floating_origin.h"
namespace astra::planetary {
// Hierarchical planetary LOD — quadtree / octahedral subdivision, screen-space error, streaming
struct TileKey { int face=0, lod=0, x=0, y=0; uint64_t hash() const { return ((uint64_t)face<<48)|((uint64_t)lod<<32)|((uint64_t)x<<16)|y; } };
struct Tile { TileKey key; float error=0; bool visible=false; bool culled_horizon=false; uint32_t resident=true; };
class PlanetaryLOD {
public:
    static constexpr int MAX_LOD = 12;
    static constexpr float SCREEN_ERROR_THRESHOLD = 1.5f; // pixels
    std::vector<Tile> select_tiles(const scene::WorldPos& cam_world, const scene::WorldPos& planet_center, double planet_radius, float fov_deg, uint32_t viewport_h);
    float screen_space_error(double distance, double tile_size, float fov, uint32_t h) const;
    bool horizon_cull(const Tile& tile, const scene::WorldPos& cam, double radius) const;
    bool frustum_cull(const Tile& tile) const { (void)tile; return false; }
    uint32_t streaming_budget(uint32_t vram_mb) const { return vram_mb<4000? 2*1024*1024 : 4*1024*1024; }
    std::string crack_free_note() const { return "skirts + T-junction fix, no cracks"; }
};
struct PlanetaryParams {
    double radius_m = 6371000;
    float height_scale = 400.f;
    std::string composition = "Earth-like N2/O2";
    float rayleigh_beta = 4e-6f, mie_beta=2.1e-5f;
    uint32_t lod = 6;
    std::string scientific_status = "SIMULATED";
};
}
