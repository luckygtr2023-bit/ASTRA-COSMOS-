
// PBR — clear-coat, sheen, HDR 16F, exposure, roughness, baseColor
namespace astra::materials {
struct PBR {
    float baseColor[3]{0.8f,0.8f,0.8f};
    float roughness=0.5f, metallic=0.0f;
    float clearcoat=0.f, sheen=0.f;
    float exposure=1.1f; // tonemap_exposure from default_env.tres
};
}
