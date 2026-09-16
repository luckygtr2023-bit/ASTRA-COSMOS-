#pragma once
#include <string>
#include <vector>
#include <cstdint>
namespace astra::rhi {
struct PipelineCache {
    std::vector<uint8_t> data;
    std::string hash;
    std::string shader_version;
    std::string compiler_version="glslang 14.0";
    bool serialize(const std::string& path); // write to disk
    bool deserialize(const std::string& path); // reuse between launches
    bool is_valid(const std::string& build_hash) const; // safe invalidation, no stale pipelines
    size_t size() const { return data.size(); }
};
}
