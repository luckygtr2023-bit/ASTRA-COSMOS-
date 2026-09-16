#pragma once
#include <string>
#include <vector>
#include <functional>
namespace astra::rhi {
// FrameGraph hardening: dependencies, barriers, transitions, lifetimes, aliasing, synchronization
enum class ResourceState { UNDEFINED, COLOR_ATTACHMENT, DEPTH_STENCIL, SHADER_READ, TRANSFER_DST, PRESENT };
enum class BarrierType { NONE, PIPELINE_BARRIER, MEMORY_BARRIER };
struct FrameGraphPass {
    std::string name;
    std::vector<std::string> reads, writes;
    ResourceState before, after;
    BarrierType barrier=BarrierType::PIPELINE_BARRIER;
};
struct HardenedFrameGraph {
    std::vector<FrameGraphPass> passes;
    void add_pass(const FrameGraphPass& p){ passes.push_back(p); }
    bool validate_dependencies() const; // ensures correct barriers, no missing transitions
    bool validate_lifetimes() const;
    bool has_no_unnecessary_barriers() const;
    size_t pass_count() const { return passes.size(); }
};
}
