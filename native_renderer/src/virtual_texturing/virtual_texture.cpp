#include "virtual_texture.h"
namespace astra::virtual_texture {
bool VirtualTextureManager::request_tile(TileKey, uint32_t){ return true; }
bool VirtualTextureManager::is_resident(TileKey) const { return true; }
void VirtualTextureManager::evict_lru(){}
}
