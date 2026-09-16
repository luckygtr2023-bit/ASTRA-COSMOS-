#pragma once
// ASTRA Native Renderer — Vulkan RHI Phase 01 Foundation (MAXIMUM-FIDELITY)
// Thin, explicit, modular, AAA-grade. Compiles with or without Vulkan SDK (guarded).
// Phase 01: instance → physical device → logical device → queues → command pools
// → sync → swapchain → render targets → HDR → descriptors → pipelines → shaders
// → resource lifetime → GPU buffers/textures/samplers → frame management → frame graph
// → bridge → camera/scene/origin → diagnostics → clean startup/shutdown

#include <cstdint>
#include <string>
#include <vector>
#include <array>
#include <optional>
#include <functional>
#include <unordered_map>
#include <memory>

#if __has_include(<vulkan/vulkan.h>)
#include <vulkan/vulkan.h>
#define ASTRA_HAS_VULKAN 1
#else
using VkInstance = void*;
using VkDevice = void*;
using VkPhysicalDevice = void*;
using VkQueue = void*;
using VkCommandPool = void*;
using VkCommandBuffer = void*;
using VkDescriptorSet = void*;
using VkDescriptorPool = void*;
using VkDescriptorSetLayout = void*;
using VkBuffer = void*;
using VkImage = void*;
using VkImageView = void*;
using VkSampler = void*;
using VkRenderPass = void*;
using VkFramebuffer = void*;
using VkPipeline = void*;
using VkPipelineLayout = void*;
using VkShaderModule = void*;
using VkSemaphore = void*;
using VkFence = void*;
using VkSwapchainKHR = void*;
using VkSurfaceKHR = void*;
using VkQueueFlags = uint32_t;
#define VK_NULL_HANDLE nullptr
#define ASTRA_HAS_VULKAN 0
// Minimal enums for static compilation
#ifndef VK_SUCCESS
#define VK_SUCCESS 0
#endif
#endif

namespace astra::rhi {

// -----------------------------------------------------------------------------
// Backend & Capability detection
// -----------------------------------------------------------------------------
enum class Backend { Vulkan13, MockHeadless };

struct VulkanVersion { uint32_t major=1, minor=3, patch=0; };

struct DeviceFeatures {
    bool samplerAnisotropy = true;
    bool descriptorIndexing = false; // bindless
    bool rayTracing = false;
    bool meshShader = false;
    bool subgroupOps = true;
    bool timelineSemaphore = true;
    bool bufferDeviceAddress = true;
};

struct DeviceInfo {
    std::string adapter_name = "Mock-Headless (no Vulkan SDK)";
    uint32_t vram_mb = 4096;
    uint32_t api_version = 0;
    bool has_validation = false;
    bool is_headless = true;
    bool is_discrete = false;
    DeviceFeatures features;
};

// -----------------------------------------------------------------------------
// Vulkan Instance — explicit, no hidden globals
// -----------------------------------------------------------------------------
struct InstanceDesc {
    std::string app_name = "ASTRA COSMOS";
    VulkanVersion app_version{0,1,0};
    bool enable_validation = true;
    bool enable_synchronization2 = true;
    std::vector<std::string> extra_extensions;
};

class VulkanInstance {
public:
    explicit VulkanInstance(const InstanceDesc& d): desc_(d) {}
    bool create(); // vkCreateInstance + debug messenger
    void destroy();
    bool is_valid() const { return valid_; }
    std::string validation_status() const { return has_validation_ ? "validation ON" : "validation OFF (mock)"; }
private:
    InstanceDesc desc_;
    bool valid_ = false;
    bool has_validation_ = false;
#if ASTRA_HAS_VULKAN
    VkInstance instance_ = VK_NULL_HANDLE;
    void* debug_messenger_ = nullptr;
#endif
};

// -----------------------------------------------------------------------------
// Physical Device Selection — prefers discrete + VRAM + feature level
// -----------------------------------------------------------------------------
struct PhysicalDeviceDesc {
    uint32_t min_vram_mb = 2048;
    bool require_anisotropy = true;
    bool prefer_discrete = true;
};

class PhysicalDeviceSelector {
public:
    struct Candidate { DeviceInfo info; int score=0; };
    std::vector<Candidate> enumerate(const VulkanInstance& inst);
    std::optional<DeviceInfo> pick_best(const VulkanInstance& inst, const PhysicalDeviceDesc& req);
private:
#if ASTRA_HAS_VULKAN
    VkPhysicalDevice chosen_ = VK_NULL_HANDLE;
#endif
};

// -----------------------------------------------------------------------------
// Logical Device + Queue Management
// -----------------------------------------------------------------------------
struct QueueFamilyIndices {
    std::optional<uint32_t> graphics;
    std::optional<uint32_t> compute;
    std::optional<uint32_t> transfer;
    std::optional<uint32_t> present;
    bool is_complete() const { return graphics.has_value(); }
};

class LogicalDevice {
public:
    struct Queue { VkQueue handle=VK_NULL_HANDLE; uint32_t family=0; };
    bool create(const DeviceInfo& info, const QueueFamilyIndices& indices, bool validation);
    void destroy();
    Queue graphics_queue() const { return graphics_; }
    Queue compute_queue() const { return compute_; }
    Queue transfer_queue() const { return transfer_; }
    bool is_valid() const { return valid_; }
private:
    bool valid_ = false;
    Queue graphics_, compute_, transfer_;
#if ASTRA_HAS_VULKAN
    VkDevice device_ = VK_NULL_HANDLE;
#endif
};

// -----------------------------------------------------------------------------
// Command Pools / Buffers — per-frame, per-thread
// -----------------------------------------------------------------------------
class CommandManager {
public:
    bool create_pool(uint32_t queue_family, bool transient);
    VkCommandBuffer allocate_primary();
    void begin_primary(VkCommandBuffer cmd, bool one_time);
    void end(VkCommandBuffer cmd);
    void reset_pool();
    void destroy();
private:
#if ASTRA_HAS_VULKAN
    VkCommandPool pool_ = VK_NULL_HANDLE;
#endif
    std::vector<VkCommandBuffer> allocated_;
};

// -----------------------------------------------------------------------------
// Synchronization — fences + semaphores + timeline
// -----------------------------------------------------------------------------
class SyncManager {
public:
    bool create_fence(bool signaled);
    bool create_semaphore();
    bool create_timeline_semaphore(uint64_t initial);
    void wait_fence(VkFence fence, uint64_t timeout_ns=1'000'000'000);
    void reset_fence(VkFence fence);
    void destroy_all();
private:
    std::vector<VkFence> fences_;
    std::vector<VkSemaphore> semaphores_;
};

// -----------------------------------------------------------------------------
// Swapchain + Render Targets + Depth + HDR Framebuffer
// -----------------------------------------------------------------------------
struct SwapchainDesc {
    uint32_t width=1920, height=1080;
    bool hdr=true; // 16F
    bool vsync=false;
    uint32_t image_count=3; // triple buffering
    bool srgb=false; // HDR uses linear
};

struct SwapchainImage { VkImage image=VK_NULL_HANDLE; VkImageView view=VK_NULL_HANDLE; };

class Swapchain {
public:
    explicit Swapchain(const SwapchainDesc& d): desc_(d) {}
    bool create(VkSurfaceKHR surface, const QueueFamilyIndices& indices);
    void destroy();
    SwapchainImage acquire_next(VkSemaphore sem);
    void present(const SwapchainImage& img, VkQueue present_queue);
    uint32_t width() const { return desc_.width; }
    uint32_t height() const { return desc_.height; }
    bool hdr() const { return desc_.hdr; }
    size_t image_count() const { return images_.size(); }
private:
    SwapchainDesc desc_;
    std::vector<SwapchainImage> images_;
#if ASTRA_HAS_VULKAN
    VkSwapchainKHR handle_ = VK_NULL_HANDLE;
#endif
};

struct RenderTargets {
    VkImage color_hdr = VK_NULL_HANDLE; // 16F
    VkImageView color_view = VK_NULL_HANDLE;
    VkImage depth = VK_NULL_HANDLE;
    VkImageView depth_view = VK_NULL_HANDLE;
    VkRenderPass render_pass = VK_NULL_HANDLE;
    VkFramebuffer framebuffer = VK_NULL_HANDLE;
    bool create(uint32_t w,uint32_t h,bool hdr);
    void destroy();
};

// -----------------------------------------------------------------------------
// Descriptor Management — pool + layouts + bindless
// -----------------------------------------------------------------------------
class DescriptorManager {
public:
    bool create_pool(uint32_t max_sets=1024);
    VkDescriptorSetLayout create_layout_bindless();
    VkDescriptorSet allocate_set(VkDescriptorSetLayout layout);
    void update_bindless(VkDescriptorSet set, uint32_t binding, VkImageView view, VkSampler sampler);
    void reset_pool();
    void destroy();
private:
#if ASTRA_HAS_VULKAN
    VkDescriptorPool pool_ = VK_NULL_HANDLE;
#endif
};

// -----------------------------------------------------------------------------
// Shader Management — GLSL → SPIR-V via glslangValidator, cache
// -----------------------------------------------------------------------------
struct ShaderDesc {
    std::string path; // e.g. shaders/terrain/heightmap_terrain.frag
    std::string entry = "main";
    bool is_compute = false;
    bool use_cache = true;
};

class ShaderManager {
public:
    struct Module { VkShaderModule handle=VK_NULL_HANDLE; std::vector<uint32_t> spirv; std::string path; };
    std::optional<Module> compile(const ShaderDesc& desc); // calls glslangValidator if available, else static check
    std::optional<Module> load_spv(const std::string& spv_path);
    void destroy_module(Module& m);
    void clear_cache();
    size_t cache_size() const { return cache_.size(); }
private:
    std::unordered_map<std::string, Module> cache_;
    std::string glslang_path_ = "/tmp/glslangValidator"; // built from /home/user/glslang
};

// -----------------------------------------------------------------------------
// Pipeline Management — graphics/compute, cache, dedup
// -----------------------------------------------------------------------------
struct GraphicsPipelineDesc {
    std::string vs, fs; // SPIR-V paths or GLSL sources
    bool depth_test=true;
    bool blend=false;
    bool wireframe=false;
    std::string debug_name;
};

struct ComputePipelineDesc {
    std::string comp;
    std::array<uint32_t,3> local_size{64,1,1};
    std::string debug_name;
};

class PipelineManager {
public:
    bool create_graphics(const GraphicsPipelineDesc& d);
    bool create_compute(const ComputePipelineDesc& d);
    VkPipeline get(const std::string& name) const;
    void bind(VkCommandBuffer cmd, const std::string& name);
    void destroy_all();
    void create_cache(); // VkPipelineCache
private:
    std::unordered_map<std::string, VkPipeline> pipelines_;
    std::unordered_map<std::string, VkPipelineLayout> layouts_;
#if ASTRA_HAS_VULKAN
    void* cache_ = nullptr; // VkPipelineCache
#endif
};

// -----------------------------------------------------------------------------
// GPU Resource Lifetime — buffers, images, samplers, pooling
// -----------------------------------------------------------------------------
class ResourcePool {
public:
    struct Buffer {
        VkBuffer handle = VK_NULL_HANDLE;
        uint64_t size = 0;
        uint32_t bindless_index = UINT32_MAX;
        bool host_visible=false;
        void* mapped=nullptr;
    };
    struct Texture {
        VkImage image=VK_NULL_HANDLE;
        VkImageView view=VK_NULL_HANDLE;
        uint32_t width=0, height=0;
        bool is_hdr=false;
    };
    struct Sampler { VkSampler handle=VK_NULL_HANDLE; bool anisotropic=true; };

    Buffer create_buffer(uint64_t bytes, uint32_t usage, bool host_visible, bool device_address);
    Texture create_texture(uint32_t w,uint32_t h,bool hdr, bool generate_mips);
    Sampler create_sampler(bool anisotropic, float max_anisotropy);
    void* map_buffer(Buffer& b);
    void unmap_buffer(Buffer& b);
    void destroy_buffer(Buffer& b);
    void destroy_texture(Texture& t);
    void destroy_sampler(Sampler& s);
    void destroy_all();
    size_t buffer_count() const { return buffers_.size(); }
private:
    std::vector<Buffer> buffers_;
    std::vector<Texture> textures_;
};

// -----------------------------------------------------------------------------
// Frame Management — N frames in flight, per-frame resources
// -----------------------------------------------------------------------------
struct FrameContext {
    uint32_t index=0;
    VkCommandBuffer cmd=VK_NULL_HANDLE;
    VkFence fence=VK_NULL_HANDLE;
    VkSemaphore image_available=VK_NULL_HANDLE;
    VkSemaphore render_finished=VK_NULL_HANDLE;
    uint64_t frame_number=0;
    bool is_recording=false;
};

class FrameManager {
public:
    static constexpr uint32_t MAX_FRAMES_IN_FLIGHT = 3;
    bool create(uint32_t count=3);
    FrameContext& begin_frame(uint32_t image_index);
    void end_frame(FrameContext& ctx);
    void wait_idle();
    void destroy();
    FrameContext& current() { return frames_[current_ % frames_.size()]; }
private:
    std::vector<FrameContext> frames_;
    uint32_t current_=0;
};

// -----------------------------------------------------------------------------
// Frame Graph — explicit passes, barriers, topological order, diagnostics
// -----------------------------------------------------------------------------
struct FrameGraphDesc {
    uint32_t width = 1920;
    uint32_t height = 1080;
    bool hdr = true;
    bool validation = true;
    uint32_t max_lights = 4096;
};

class FrameGraph {
public:
    using PassFn = std::function<void(VkCommandBuffer)>;
    struct Pass { std::string name; PassFn fn; std::vector<std::string> depends; };

    void add_pass(const std::string& name, PassFn fn, std::vector<std::string> deps={});
    void execute(VkCommandBuffer cmd); // topological + barriers
    void clear() { passes_.clear(); }
    size_t pass_count() const { return passes_.size(); }
    std::vector<std::string> pass_names() const;
private:
    std::vector<Pass> passes_;
};

// -----------------------------------------------------------------------------
// Top-level Vulkan RHI — composes all managers, clean startup/shutdown
// -----------------------------------------------------------------------------
class VulkanRHI {
public:
    explicit VulkanRHI(const FrameGraphDesc& desc);
    ~VulkanRHI();

    // Full lifecycle — modular, each step logs
    bool init(); // instance→physical→logical→queues→command→sync→swapchain→targets→descriptors→pipelines
    void shutdown(); // reverse order, no leaks
    DeviceInfo query_device() const { return device_info_; }
    bool is_headless() const { return headless_; }
    bool has_vulkan() const { return has_vulkan_; }

    // Instance/device/queue access (for diagnostics)
    VulkanInstance& instance() { return *instance_; }
    LogicalDevice& device() { return *logical_device_; }
    Swapchain& swapchain() { return *swapchain_; }
    FrameManager& frames() { return *frame_manager_; }
    FrameGraph& graph() { return *frame_graph_; }
    ShaderManager& shaders() { return *shader_manager_; }
    PipelineManager& pipelines() { return *pipeline_manager_; }
    DescriptorManager& descriptors() { return *descriptor_manager_; }
    ResourcePool& resources() { return *resource_pool_; }

    // Legacy thin wrappers (used by main.cpp)
    using PassFn = FrameGraph::PassFn;
    void add_pass(const std::string& name, PassFn fn) { frame_graph_->add_pass(name, fn); }
    void execute_graph(VkCommandBuffer cmd) { frame_graph_->execute(cmd); }
    void present();

    // Legacy GPU resources
    struct Buffer { VkBuffer handle = VK_NULL_HANDLE; uint64_t size=0; uint32_t bindless_index=UINT32_MAX; };
    Buffer create_buffer(uint64_t bytes, uint32_t usage, bool host_visible) {
        auto b = resource_pool_->create_buffer(bytes, usage, host_visible, false);
        return {b.handle, b.size, b.bindless_index};
    }
    void destroy_buffer(Buffer& b) { ResourcePool::Buffer rb{b.handle,b.size,b.bindless_index,false,nullptr}; resource_pool_->destroy_buffer(rb); b.handle=VK_NULL_HANDLE; }

    void dispatch_compute(VkCommandBuffer cmd, uint32_t x, uint32_t y, uint32_t z);

    static constexpr uint64_t STREAM_BUDGET_BYTES = 4 * 1024 * 1024;
    static constexpr uint64_t TILE_BYTES = 256 * 1024;

    struct Telemetry {
        float fps=60.f, avg60=60.f;
        uint32_t draw_calls=0, visible_instances=0, culled=0;
        uint32_t vram_used_mb=0, buffer_count=0;
        uint64_t frame_number=0;
    };
    Telemetry tick_telemetry();

    // Error handling
    enum class Error { None, InstanceFailed, NoPhysicalDevice, DeviceFailed, SwapchainFailed, ShaderCompileFailed };
    Error last_error() const { return last_error_; }
    std::string last_error_str() const;

    // Debug
    void dump_diagnostics() const; // prints to stdout for Tracy/RenderDoc hooks

private:
    FrameGraphDesc desc_;
    DeviceInfo device_info_;
    bool has_vulkan_ = ASTRA_HAS_VULKAN;
    bool headless_ = true;
    Error last_error_ = Error::None;

    std::unique_ptr<VulkanInstance> instance_;
    std::unique_ptr<PhysicalDeviceSelector> selector_;
    std::unique_ptr<LogicalDevice> logical_device_;
    std::unique_ptr<CommandManager> command_manager_;
    std::unique_ptr<SyncManager> sync_manager_;
    std::unique_ptr<Swapchain> swapchain_;
    std::unique_ptr<RenderTargets> render_targets_;
    std::unique_ptr<DescriptorManager> descriptor_manager_;
    std::unique_ptr<ShaderManager> shader_manager_;
    std::unique_ptr<PipelineManager> pipeline_manager_;
    std::unique_ptr<ResourcePool> resource_pool_;
    std::unique_ptr<FrameManager> frame_manager_;
    std::unique_ptr<FrameGraph> frame_graph_;
    QueueFamilyIndices queue_indices_;
};

} // namespace astra::rhi
