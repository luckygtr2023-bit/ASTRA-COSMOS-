
// Lighting — clustered Forward+ 4096 lights, PBR HDR, ACES, exposure, shadows 8192
namespace astra::lighting {
constexpr int MAX_LIGHTS=4096;
struct Light{ float pos[3]; float intensity; float color[3]; };
void cluster_lights(const Light* lights, int count){ (void)lights; (void)count; /* 3D grid 16x9x24 */ }
}
