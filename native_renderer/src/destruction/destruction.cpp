
#include "destruction.h"
namespace astra::destruction {
DestructionConfig detect_config(uint32_t vram){ DestructionConfig c; c.rbd_enabled = vram>=4000; c.max_fragments = vram>=8000?4096:1024; return c; }
std::string scientific_state_preserved(){ return "Renderer visual debris does not overwrite astra.core mass/velocity"; }
}
