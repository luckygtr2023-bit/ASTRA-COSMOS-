#pragma once
#include <string>
#include <cstdint>
namespace astra::streaming {
enum class MaterialType { ALBEDO, NORMAL, ROUGHNESS, METALLIC, EMISSION, HEIGHT, ENVIRONMENT };
struct MaterialRequest {
    MaterialType type;
    std::string asset_id;
    float screen_size=0;
    float distance=0;
    bool visible=true;
    float importance=1.f;
    bool focused=false;
};
float material_priority(const MaterialRequest& r);
uint32_t mip_for_distance(float dist, uint32_t max_mip);
std::string fallback_texture();
}
