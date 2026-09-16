#include "rhi/vulkan_rhi.h"
#include "scene/floating_origin.h"
#include <cstdio>
#include <vector>

// ASTRA Native — main entry, headless + windowed, deterministic, 60Hz
// Bridge: reads bridge_state.json hash compare like Godot AstraBridge

int main(int argc, char** argv){
    bool headless = false;
    for(int i=1;i<argc;i++) if(std::string(argv[i])=="--headless") headless=true;
    std::printf("[ASTRA Native] C++20 Vulkan 1.3 headless=%d\n", headless);

    // RHI init
    astra::rhi::FrameGraphDesc desc; desc.width=1920; desc.height=1080; desc.hdr=true;
    astra::rhi::VulkanRHI rhi(desc);
    rhi.init();
    auto info = rhi.query_device();
    std::printf("[RHI] adapter=%s vram=%u validation=%d headless=%d\n", info.adapter_name.c_str(), info.vram_mb, info.has_validation, info.is_headless);

    // Floating-origin 5 scales test (deterministic, mirrors validate_coordinates.py)
    bool fo_ok = astra::scene::OriginRebaser::test_five_scales();
    std::printf("[FloatingOrigin] five scales %s\n", fo_ok?"OK":"FAIL");

    // Scene hierarchy 52,0,0
    astra::scene::SceneHierarchy hier; hier.build_deterministic();
    bool h_ok = hier.test_52();
    auto wpos = hier.world_pos("DeterministicTestObject");
    std::printf("[Hierarchy] world 52,0,0 got %.1f,%.1f,%.1f %s\n", wpos.x,wpos.y,wpos.z, h_ok?"OK":"FAIL");

    // FrameGraph passes (AAA)
    rhi.add_pass("shadow", [](auto){ /* 8192 PSSM */ });
    rhi.add_pass("terrain", [](auto){ /* heightmap_terrain 400 */ });
    rhi.add_pass("atmosphere", [](auto){ /* Rayleigh 4e-6 Mie 2.1e-5 */ });
    rhi.add_pass("stars_indirect", [](auto){ /* 10k indirect */ });
    rhi.add_pass("galaxy_spiral", [](auto){ /* b=0.22 */ });
    rhi.add_pass("blackhole_raymarch", [](auto){ /* 256 steps */ });
    rhi.add_pass("lensing", [](auto){ /* alpha 2rs/b */ });
    rhi.add_pass("vfx", [](auto){ /* 1M particles */ });
    rhi.add_pass("postprocess", [](auto){ /* AgX + bloom 0.8 */ });

    // Telemetry every 60
    for(int i=0;i<120;i++){
        auto tel = rhi.tick_telemetry();
        if(i%60==0) std::printf("[Telemetry] fps=%.1f avg60=%.1f draw=%u\n", tel.fps, tel.avg60, tel.draw_calls);
    }

    rhi.shutdown();
    std::printf("[ASTRA Native] %s headless quit\n", (fo_ok && h_ok)?"OK":"FAIL");
    return (fo_ok && h_ok)?0:1;
}
