#include "pipeline_cache.h"
#include <fstream>
namespace astra::rhi {
bool PipelineCache::serialize(const std::string& p){
    std::ofstream f(p, std::ios::binary);
    if(!f) return false;
    f.write((char*)data.data(), data.size());
    return true;
}
bool PipelineCache::deserialize(const std::string& p){
    std::ifstream f(p, std::ios::binary);
    if(!f) return false;
    data.assign((std::istreambuf_iterator<char>(f)), {});
    return true;
}
bool PipelineCache::is_valid(const std::string& h) const { return hash==h; }
}
