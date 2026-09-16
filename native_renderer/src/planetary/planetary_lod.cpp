#include "planetary_lod.h"
#include <cmath>
namespace astra::planetary {
std::vector<Tile> PlanetaryLOD::select_tiles(const scene::WorldPos& cam, const scene::WorldPos& center, double radius, float fov, uint32_t h){
    std::vector<Tile> out;
    double dist = std::sqrt((cam.x-center.x)*(cam.x-center.x)+(cam.y-center.y)*(cam.y-center.y)+(cam.z-center.z)*(cam.z-center.z));
    int lod = 0;
    if(dist < radius*1.2) lod=8;
    else if(dist < radius*3) lod=6;
    else if(dist < radius*10) lod=3;
    for(int face=0;face<6;face++) for(int x=0;x<(1<<lod);x++) for(int y=0;y<(1<<lod);y++) {
        Tile t{{face,lod,x,y}, 0, true, false, true};
        t.error = screen_space_error(dist, radius/(1<<lod), fov, h);
        t.visible = t.error > SCREEN_ERROR_THRESHOLD;
        out.push_back(t);
        if(out.size()> 1024) return out;
    }
    return out;
}
float PlanetaryLOD::screen_space_error(double dist, double tile_sz, float fov, uint32_t h) const {
    double proj = tile_sz / std::max(dist,1.0) * (h / (2*std::tan(fov*3.14159/360)));
    return float(proj);
}
bool PlanetaryLOD::horizon_cull(const Tile& t, const scene::WorldPos& cam, double r) const {
    (void)t;(void)cam;(void)r; return false;
}
}
