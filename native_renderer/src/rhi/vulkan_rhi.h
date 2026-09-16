#pragma once
// ASTRA Native Renderer — Vulkan RHI Abstraction (thin, explicit, AAA-grade)
// Design: explicit BAR, FrameGraph, bindless where justified, async compute.
// This header is implementable without Vulkan SDK (guarded), compiles with g++ -std=c++20 even if vulkan.h missing (fallback defines).

#include <cstdint>
#include <string>
#include <vector>
#include <array>
#include <optional>
#include <functional>

#if __has_include(<vulkan/vulkan.h>)
#include <vulkan/vulkan.h>
#define ASTRA_HAS_VULKAN 1
#else
// Minimal forward decls for static compilation without SDK
using VkInstance = void*;
using VkDevice = void*;
using VkPhysicalDevice = void*;
using VkQueue = void*;
using VkCommandBuffer = void*;
using VkDescriptorSet = void*;
using VkBuffer = void*;
using VkImage = void*;
#define VK_NULL_HANDLE nullptr
#define ASTRA_HAS_VULKAN 0
#endif

namespace astra::rhi {

enum class Backend { Vulkan13, MockHeadless };

struct DeviceInfo {
    std::string adapter_name = "Mock-Headless (no Vulkan SDK)";
    uint32_t vram_mb = 4096;
    bool has_validation = false;
    bool is_headless = true;
};

struct FrameGraphDesc {
    uint32_t width = 1920;
    uint32_t height = 1080;
    bool hdr = true; // 16F
    bool validation = true;
    uint32_t max_lights = 4096; // clustered Forward+ matching Godot
};

class VulkanRHI {
public:
    explicit VulkanRHI(const FrameGraphDesc& desc);
    ~VulkanRHI();

    // Lifecycle — explicit, no hidden globals
    bool init(); // returns false if Vulkan SDK not available → mock headless (still static-valid)
    void shutdown();
    DeviceInfo query_device() const;

    // FrameGraph — AAA: passes are explicit, not hidden like Godot
    using PassFn = std::function<void(VkCommandBuffer)>;
    void add_pass(const std::string& name, PassFn fn);
    void execute_graph(VkCommandBuffer cmd); // orders passes topologically
    void present(); // swapchain

    // GPU resources — explicit BAR, bindless
    struct Buffer {
        VkBuffer handle = VK_NULL_HANDLE;
        uint64_t size = 0;
        uint32_t bindless_index = UINT32_MAX; // for bindless textures
    };
    Buffer create_buffer(uint64_t bytes, uint32_t usage, bool host_visible);
    void destroy_buffer(Buffer& b);

    // Compute — async queue for BH / instance culling
    void dispatch_compute(VkCommandBuffer cmd, uint32_t x, uint32_t y, uint32_t z); // local_size 256

    // Streaming — 4MB/frame budget, 256KB tile
    static constexpr uint64_t STREAM_BUDGET_BYTES = 4 * 1024 * 1024;
    static constexpr uint64_t TILE_BYTES = 256 * 1024;

    // Telemetry — mirrors Godot Telemetry every 60 frames
    struct Telemetry {
        float fps = 0.f;
        float avg60 = 0.f;
        uint32_t draw_calls = 0;
        uint32_t visible_instances = 0;
        uint32_t culled = 0;
    };
    Telemetry tick_telemetry(); // call every 60 frames

    bool is_headless() const { return headless_; }
    bool has_vulkan() const { return has_vulkan_; }

private:
    FrameGraphDesc desc_;
    DeviceInfo info_;
    bool has_vulkan_ = ASTRA_HAS_VULKAN;
    bool headless_ = true;
    std::vector<std::pair<std::string, PassFn>> passes_;
};

} // namespace astra::rhi
