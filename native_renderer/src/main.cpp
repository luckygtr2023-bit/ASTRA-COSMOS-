#include "rhi/vulkan_rhi.h"
#include "scene/floating_origin.h"
#include "scene/scene.h"
#include "audio/cosmic_audio_engine.h"
#include "audio/solar/solar_audio.h"
#include "audio/black_hole/black_hole_audio.h"
#include "audio/pulsar/pulsar_audio.h"
#include "mcp/astra_mcp.h"
#include "rt/ray_traced.h"
#include "mesh_shader/virtual_geo.h"
#include "destruction/destruction.h"
#include "materials8k/materials8k.h"
#include <cstdio>
#include <vector>
#include <string>

int main(int argc, char** argv){
    bool headless = false;
    bool benchmark = false;
    bool validate_only = false;
    for(int i=1;i<argc;i++){
        std::string a=argv[i];
        if(a=="--headless") headless=true;
        if(a=="--benchmark") benchmark=true;
        if(a=="--validate") validate_only=true;
    }
    std::printf("[ASTRA Native] C++20 Vulkan 1.3 Phase01+Audio headless=%d benchmark=%d\n", headless, benchmark);

    // 1. RHI
    astra::rhi::FrameGraphDesc desc;
    desc.width=1920; desc.height=1080; desc.hdr=true; desc.validation=true; desc.max_lights=4096;
    astra::rhi::VulkanRHI rhi(desc);
    bool ok = rhi.init();
    if(!ok) std::printf("[RHI] init failed: %s\n", rhi.last_error_str().c_str());
    auto info = rhi.query_device();
    std::printf("[RHI] adapter=%s vram=%u validation=%d headless=%d has_vulkan=%d error=%s\n",
        info.adapter_name.c_str(), info.vram_mb, info.has_validation, info.is_headless, rhi.has_vulkan(), rhi.last_error_str().c_str());
    rhi.dump_diagnostics();

    // 2. Floating-origin
    bool fo_ok = astra::scene::OriginRebaser::test_five_scales();
    std::printf("[FloatingOrigin] five scales %s\n", fo_ok?"OK":"FAIL");
    astra::scene::Scene scene;
    scene.rebaser.current_origin = {1e11,0,0};
    scene.state.objects.push_back({"star-1","STAR",{1e11+50,0,0},"world","REAL",0,1.989e30,0});
    auto rel = scene.gpu_positions();
    bool rel_ok = !rel.empty() && rel[0][0] == 50.f;
    std::printf("[RenderState] world_to_relative 50 %s\n", rel_ok?"OK":"FAIL");

    // 3. Hierarchy
    astra::scene::SceneHierarchy hier; hier.build_deterministic();
    bool h_ok = hier.test_52();
    auto wpos = hier.world_pos("DeterministicTestObject");
    std::printf("[Hierarchy] world 52,0,0 got %.1f,%.1f,%.1f %s\n", wpos.x,wpos.y,wpos.z, h_ok?"OK":"FAIL");

    // 4. Shaders
    int shader_ok = 0, shader_fail=0;
    const char* shaders[] = {
        "native_renderer/shaders/terrain/heightmap_terrain.frag",
        "native_renderer/shaders/atmosphere/rayleigh_mie.frag",
        "native_renderer/shaders/ocean/gerstner_ocean.vert",
        "native_renderer/shaders/stars/procedural_starfield.frag",
        "native_renderer/shaders/galaxy/spiral_galaxy.frag",
        "native_renderer/shaders/black_hole/raymarch.comp",
        "native_renderer/shaders/lensing/gravitational_lensing.frag",
        "native_renderer/shaders/vfx/impact_spark.comp",
        "native_renderer/shaders/compute/instance_prepare.comp",
        "native_renderer/shaders/compute/culling.comp",
        "native_renderer/shaders/postprocess/tonemap_bloom.comp"
    };
    for(auto* p: shaders){
        auto mod = rhi.shaders().compile({p, "main", std::string(p).find(".comp")!=std::string::npos});
        if(mod) shader_ok++; else { shader_fail++; std::printf("[Shader] FAIL %s\n", p); }
    }
    std::printf("[Shader] compiled %d ok %d fail (glslangValidator %s)\n", shader_ok, shader_fail, "/tmp/glslangValidator");

    // 5. Pipelines
    rhi.pipelines().create_graphics({"vs","fs",true,false,false,"terrain"});
    rhi.pipelines().create_compute({"native_renderer/shaders/black_hole/raymarch.comp", {64,1,1}, "bh_raymarch"});
    rhi.pipelines().create_compute({"native_renderer/shaders/compute/instance_prepare.comp", {256,1,1}, "instance_prepare"});
    rhi.pipelines().create_compute({"native_renderer/shaders/compute/culling.comp", {64,1,1}, "culling"});
    std::printf("[Pipeline] 4 pipelines + cache ready\n");

    // 6. Resources
    auto staging = rhi.resources().create_buffer(4*1024*1024, 0x80, true, false);
    auto gpuBuf = rhi.resources().create_buffer(10*1024*1024, 0x80, false, true);
    auto hdrTex = rhi.resources().create_texture(1920,1080,true,true);
    auto sampler = rhi.resources().create_sampler(true, 16.f);
    std::printf("[Resources] staging %llu gpu %llu hdr %ux%u sampler aniso\n",
        (unsigned long long)staging.size, (unsigned long long)gpuBuf.size, hdrTex.width, hdrTex.height);

    // 7. FrameGraph
    rhi.add_pass("shadow", [](auto cmd){ (void)cmd; });
    rhi.add_pass("terrain", [](auto cmd){ (void)cmd; });
    rhi.add_pass("atmosphere", [](auto cmd){ (void)cmd; });
    rhi.add_pass("ocean", [](auto cmd){ (void)cmd; });
    rhi.add_pass("stars_indirect", [](auto cmd){ (void)cmd; });
    rhi.add_pass("galaxy_spiral", [](auto cmd){ (void)cmd; });
    rhi.add_pass("blackhole_raymarch", [](auto cmd){ (void)cmd; });
    rhi.add_pass("lensing", [](auto cmd){ (void)cmd; });
    rhi.add_pass("vfx", [](auto cmd){ (void)cmd; });
    rhi.add_pass("postprocess", [](auto cmd){ (void)cmd; });
    std::printf("[FrameGraph] %zu passes registered\n", rhi.graph().pass_count());

    // 8. Frame loop
    for(int i=0;i<120;i++){
        auto& frame = rhi.frames().current();
        auto tel = rhi.tick_telemetry();
        if(i%60==0) std::printf("[Telemetry] frame=%llu fps=%.1f avg60=%.1f draw=%u visible=%u vram=%u buffers=%u\n",
            (unsigned long long)tel.frame_number, tel.fps, tel.avg60, tel.draw_calls, tel.visible_instances, tel.vram_used_mb, tel.buffer_count);
        if(i==60 && benchmark) std::printf("[Benchmark] 60 frames simulated 5.2ms target vs 16.6 budget (mock, would use VkQueryPool + Tracy)\n");
        (void)frame;
    }

    // 9. Diagnostics + quality tiers
    rhi.dump_diagnostics();
    const char* tier = "HIGH";
    if(info.vram_mb >= 12000 && info.features.descriptorIndexing) tier="ULTRA";
    else if(info.vram_mb >= 8000) tier="HIGH";
    else if(info.vram_mb >= 4000) tier="MEDIUM";
    else tier="LOW";
    if(rhi.is_headless()) tier="SAFE (headless mock)";
    std::printf("[QualityTier] detected %s (VRAM %u, bindless %d, headless %d)\n", tier, info.vram_mb, info.features.descriptorIndexing, rhi.is_headless());
    if(validate_only) std::printf("[ValidateOnly] Phase01 validation complete — no present\n");

    // 10. Cosmic Audio Engine
    astra::audio::CosmicAudioEngine audio;
    audio.init(true);
    astra::audio::AudioFrame af; af.tick=42; af.sim_time_s=1234.5;
    af.sources.push_back(astra::audio::solar::solar_oscillations(3000, astra::audio::AudioQuality::SCIENTIFIC));
    af.sources.push_back(astra::audio::black_hole::bh_merger_gw("GW150914_mock", 28.1, false));
    af.sources.push_back(astra::audio::pulsar::pulsar_timing("PSR_B0531+21", 33.0, "Jodrell Bank", true));
    audio.push_frame(af);
    auto synth = audio.tick_synthesis();
    std::printf("[CosmicAudio] backend=%s active=%u queue=%zu cpu=%.2fms validated=%d\n", audio.backend().c_str(), synth.active_sources, audio.queue_size(), synth.cpu_ms, audio.validate_no_mislabel()?1:0);
    auto hear = audio.hear_universe({"earth","pulsar","black_hole","wormhole"});
    std::printf("[HearUniverse] %zu sources auto\n", hear.size());
    for(auto& s: hear) std::printf("  - %s %s %s provenance %s\n", s.id.c_str(), s.provenance.object_type.c_str(), astra::audio::truth_to_string(s.truth).c_str(), s.provenance.dataset.c_str());
    astra::mcp::AstraMCPServer mcp; mcp.init_default_tools();
    std::printf("[MCP] tools %zu: ", mcp.list_tools().size()); for(auto& t: mcp.list_tools()) std::printf("%s ", t.c_str()); std::printf("\n");
    {
        auto rt = astra::rt::detect_rt_config(info.vram_mb, info.features.rayTracing);
        auto mesh = astra::mesh_shader::detect_config(info.vram_mb, info.features.meshShader);
        auto dest = astra::destruction::detect_config(info.vram_mb);
        auto ktx = astra::materials8k::config_for_tier(astra::materials8k::Tier::HIGH);
        std::printf("[RT] enabled=%d quality=%d fallback=%s\n", rt.enabled, (int)rt.quality, fallback_path(rt).c_str());
        std::printf("[VirtualGeo] enabled=%d budget=%u\n", mesh.enabled, astra::mesh_shader::streaming_budget(info.vram_mb));
        std::printf("[Destruction] rbd=%d fragments=%u preserved=%s\n", dest.rbd_enabled, dest.max_fragments, astra::destruction::scientific_state_preserved().c_str());
        std::printf("[Materials8K] res=%u tile=%u need8k=%d budget=%u\n", ktx.max_res, ktx.tile, needs_8k(astra::materials8k::Tier::CINEMATIC), astra::materials8k::streaming_budget(info.vram_mb));
    }
    audio.shutdown();

    // 11. Clean shutdown
    rhi.resources().destroy_buffer(staging);
    rhi.resources().destroy_buffer(gpuBuf);
    rhi.resources().destroy_texture(hdrTex);
    rhi.resources().destroy_sampler(sampler);
    rhi.shutdown();
    bool all_ok = fo_ok && h_ok && rel_ok && shader_fail==0;
    std::printf("[ASTRA Native] %s Phase01+Audio shutdown ok (shaders %d/%d)\n", all_ok?"OK":"FAIL", shader_ok, shader_ok+shader_fail);
    return all_ok?0:1;
}
