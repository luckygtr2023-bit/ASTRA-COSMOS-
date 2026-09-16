
// GPU — explicit BAR, bindless, persistent, descriptor management
#include <cstdint>
#include <vector>
namespace astra::gpu {
struct Buffer {
    uint64_t size=0;
    uint32_t bindless_idx=0xffffffffu;
    void* mapped=nullptr;
    bool host_visible=false;
    void create(uint64_t sz,bool host){ size=sz; host_visible=host; }
    void destroy(){ size=0; }
};
struct DescriptorPool {
    static constexpr uint32_t MAX_SETS=4096;
    uint32_t allocated=0;
    uint32_t allocate(){ return allocated++; }
};
}
