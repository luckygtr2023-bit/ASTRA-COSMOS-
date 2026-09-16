#pragma once
#include <cstdint>
namespace astra::virtual_texture {
struct TileKey { uint32_t x,y,mip; uint64_t hash() const { return ((uint64_t)mip<<40)|(x<<20)|y; } };
struct Residency { bool resident=false; uint32_t priority=0; };
class VirtualTextureManager {
public:
    bool request_tile(TileKey k, uint32_t priority);
    bool is_resident(TileKey k) const;
    void evict_lru();
    uint32_t resident_count() const { return 512; }
    uint32_t budget_bytes(uint32_t vram) const { return vram<4000? 256*1024*1024 : 1024*1024*1024; }
};
}
