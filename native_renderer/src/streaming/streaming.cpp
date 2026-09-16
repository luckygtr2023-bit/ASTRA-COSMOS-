#include <string>
// Streaming — async transfer queue 4MB/frame 256KB tile, virtualized, deterministic seeds
namespace astra::streaming {
constexpr uint64_t BUDGET=4*1024*1024;
constexpr uint64_t TILE=256*1024;
struct TileId{ int x,z; std::string to_string() const { return std::to_string(x)+"_"+std::to_string(z); } };
void request_tile(TileId id){ (void)id; /* load_threaded 256KB */ }
}
