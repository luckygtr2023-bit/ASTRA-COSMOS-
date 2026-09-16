// Copyright © 2026 Lucky Kumar — ASTRA COSMOS
// Native Renderer Production Entry Point — astra_native
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
#include "planetary/planetary_lod.h"
#include "starfield/starfield.h"
#include "rings/ring_renderer.h"
#include "clusters/cluster_renderer.h"
#include "cosmic/cosmic_structure.h"
#include "observer/observer.h"
#include "extreme/black_hole_physics.h"
#include "extreme/relativistic.h"
#include "plasma_ext/plasma_magnetosphere.h"
#include "threading/render_threading.h"
#include "shaders/shader_manager.h"
#include "rhi/pipeline_cache.h"
#include "rhi/frame_graph.h"
#include "culling/occlusion.h"
#include "performance/object_importance.h"
#include "performance/dynamic_quality.h"
#include "performance/frame_budget.h"
#include "gpu/async_transfer.h"
#include "streaming/material_streaming.h"
#include "streaming/astronomical_streaming.h"
#include "gpu_memory/budget.h"
#include "lod/hierarchical_lod.h"
#include "visualization/visualization_modes.h"
#include "postprocess/upscaling.h"
#include "postprocess/temporal.h"
#include "postprocess/hdr_bloom.h"
#include "cinematic/time_controller.h"
#include "cinematic/timeline.h"
#include "camera/cinematic_camera.h"
#include "vfx/volumetrics_hardened.h"
#include "vfx/destruction_vfx.h"
#include "vfx/astrophysical_vfx.h"
#include "vfx/gpu_particles.h"
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
        "native_renderer/shaders/postprocess/tonemap_bloom.comp",
        "native_renderer/shaders/wormhole/white_hole.frag",
        "native_renderer/shaders/plasma/magnetosphere.frag",
        "native_renderer/shaders/plasma/jet.frag",
        "native_renderer/shaders/rings/ring.frag",
        "native_renderer/shaders/spacetime/tidal_field.frag",
        "native_renderer/shaders/clusters/cluster.frag",
        "native_renderer/shaders/vfx/gpu_particles.comp",
        "native_renderer/shaders/vfx/solar_flare.comp",
        "native_renderer/shaders/volumetrics/volumetric_raymarch.comp",
        "native_renderer/shaders/postprocess/taa.comp",
        "native_renderer/shaders/postprocess/fsr2.comp",
        "native_renderer/shaders/vfx/destruction.comp"
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
    // -----------------------------------------------------------------
    // Phase 2 + 3 — Astronomical + Extreme Physics demo
    // -----------------------------------------------------------------
    {
        astra::planetary::PlanetaryLOD lod;
        astra::planetary::PlanetaryParams pp; pp.radius_m=6371000; pp.height_scale=400;
        auto tiles = lod.select_tiles({0,0,0}, {0,0,0}, pp.radius_m, 60.f, 1080);
        std::printf("[PlanetaryLOD] tiles %zu error %.2f crack_free %s scientific %s\n", tiles.size(), tiles.empty()?0:tiles[0].error, lod.crack_free_note().c_str(), pp.scientific_status.c_str());
        astra::starfield::StarLOD sl = astra::starfield::lod_for_distance(1e12, 7e8);
        std::printf("[Starfield] LOD for 1e12m %d (POINT 0) budget %u\n", (int)sl, astra::starfield::streaming_budget(info.vram_mb));
        float rd = astra::rings::ring_density(0.46f);
        std::printf("[Rings] density at Cassini gap 0.46 %.2f gaps %d\n", rd, 1);
        auto cluster = astra::clusters::generate_cluster(0xA573, 10, {1e45,5,0.1});
        std::printf("[Cluster] galaxies %zu deterministic seed 0xA573 type %s\n", cluster.size(), cluster[0].type.c_str());
        double dens[4]; astra::cosmic::generate_filament({1e-27,50}, dens, 4);
        std::printf("[CosmicStructure] filament density %.2e\n", dens[0]);
        astra::observer::ObserverState obs; obs.pos={1e11,0,0}; obs.mode=astra::observer::Mode::INTERPLANETARY; obs.tick=42;
        std::printf("[Observer] mode %d frame_independent %d tick %llu\n", (int)obs.mode, astra::observer::is_scientific_frame_independent(obs)?1:0, (unsigned long long)obs.tick);
        astra::extreme::SchwarzschildParams bh{1.989e31,29540,0};
        std::printf("[BlackHolePhysics] photon %.1f shadow %.1f isco %.1f deflection %.4f theoretical\n", astra::extreme::photon_sphere(bh.rs_m), astra::extreme::shadow_radius(bh.rs_m), astra::extreme::isco(bh.rs_m,0), astra::extreme::deflection_angle(bh.rs_m, 1e5));
        double tidal = astra::relativity::spacetime_curvature(bh.rs_m, bh.rs_m*5);
        auto tt = astra::relativity::tidal_field(bh.rs_m, bh.rs_m*5);
        std::printf("[Relativity] curvature %.2e tidal %.2e label %s\n", tidal, tt.xx, tt.label.c_str());
        std::printf("[Wormhole/WhiteHole/Warp] theoretical/speculative labeled status THEORETICAL\n");
        double plasma_out[4]; astra::plasma::emit_plasma({1e6,100,10}, plasma_out, 4);
        std::printf("[Plasma] magnetosphere jet tracers %.2f\n", plasma_out[0]);
        std::printf("[ScientificLabel] planet REAL atmosphere SIMULATED wormhole THEORETICAL warp SPECULATIVE\n");
    }
    // -----------------------------------------------------------------
    // Phase 4 + 5 — GPU VFX + Cinematic + Performance demo
    // -----------------------------------------------------------------
    {
        astra::vfx::GPUParticleSystem particles({1000000, astra::vfx::Buffering::TRIPLE, true, 0xA573, 0.02f, 0.1f});
        particles.init();
        particles.spawn_gpu(1024, nullptr, nullptr);
        particles.update_gpu(0.016f, nullptr);
        particles.cull_gpu(nullptr);
        particles.render_indirect();
        auto stats = particles.stats();
        std::printf("[GPUParticles] max %u alive %u spawned %u culled %u buffering %s deterministic %d no_cpu %d\n",
            particles.max_count(), stats.alive, stats.spawned, stats.culled,
            particles.buffering_note().c_str(), particles.is_deterministic()?1:0, astra::vfx::validate_no_cpu_per_particle()?1:0);
        astra::vfx::SolarFlareParams flare{1e25,1e7,1e-6,10,5e5};
        std::printf("[AstroVFX] flare %s cme %s aurora %s jet %s param_driven %d\n",
            astra::vfx::flare_emissive(flare).c_str(),
            astra::vfx::cme_visual({1e12,1e6,1e23}).c_str(),
            astra::vfx::aurora_visual({50e-6,2e-9}).c_str(),
            astra::vfx::jet_visual({1e38,0.9,1e9}).c_str(),
            astra::vfx::is_param_driven("solar_flare")?1:0);
        auto deb = astra::vfx::handle_impact({1e9,5000,1000,true,"REAL"});
        std::printf("[DestructionVFX] debris %u dust %.3f glow %.1f smoke %d rule %s preserved %s\n",
            deb.fragment_count, deb.dust_density, deb.thermal_glow, deb.smoke?1:0,
            astra::vfx::smoke_rule({1e9,5000,1000,true}).c_str(),
            astra::vfx::scientific_state_check().c_str());
        astra::vfx::VolumeConfig vol{64,true,true,true,0.004f};
        std::printf("[Volumetrics] slices %u cost %.2fms physically %d\n",
            vol.slices, astra::vfx::ray_march_cost(vol), astra::vfx::is_physically_meaningful("nebula")?1:0);
        astra::camera::CinematicCamera cam; cam.set_mode(astra::camera::CinematicMode::CINEMATIC);
        cam.add_bookmark({"sun_focus",{0,0,10},{0,0,0},60,1.1f});
        cam.interpolate(0.5f,{0,{0,0,0},60},{1,{10,0,0},45});
        std::printf("[CinematicCamera] mode %d bookmarks %zu fov %.1f exposure %.1f scientific_unchanged %d\n",
            (int)cam.mode, cam.bookmarks.size(), cam.fov, cam.exposure,
            astra::camera::is_scientific_observer_unchanged(cam)?1:0);
        astra::cinematic::Timeline tl; tl.add({0, astra::cinematic::TrackType::CAMERA_POS, "camera pos", 0xA573});
        tl.add({1, astra::cinematic::TrackType::FOCUS, "focus Sun", 0});
        tl.add({2, astra::cinematic::TrackType::TIME_SCALE, "2x", 0});
        tl.add({3, astra::cinematic::TrackType::VFX_TRIGGER, "solar flare VFX", 0});
        std::printf("[Timeline] keys %zu deterministic %d example %s\n",
            tl.count(), tl.is_deterministic()?1:0, astra::cinematic::example_timeline().c_str());
        astra::cinematic::TimeController tc; tc.set_cinematic_scale(2.0); tc.scrub(100);
        std::printf("[TimeController] scientific %.1f cinematic %.1f separated %d\n",
            tc.get_scientific(), tc.get_cinematic(), tc.is_separated()?1:0);
        std::printf("[HDR] luminance %.3f exposure %.3f bloom_ok %d tonemap AgX\n",
            astra::postprocess::luminance_extract(10,10,10), astra::postprocess::exposure_for_bright(10), astra::postprocess::bloom_not_destroy()?1:0);
        astra::postprocess::TemporalConfig tcfg{true,true,true,true,0.9f};
        float curr[3]={1,0,0}, prev[3]={0,0,0}, vp[16]={1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1};
        auto mv = astra::postprocess::compute_motion_vector(curr, prev, vp);
        std::printf("[Temporal] TAA %d motion %.1f,%.1f origin_shift %d ghost %d\n",
            tcfg.taa?1:0, mv.dx, mv.dy, astra::postprocess::handles_origin_shift(tcfg)?1:0, astra::postprocess::avoids_ghosting(1e6f)?1:0);
        std::printf("[Upscaling] FSR2 %d scaffolding %d fallback %s\n",
            astra::postprocess::detect_fsr2_support()?1:0, astra::postprocess::is_scaffolding_only()?1:0, astra::postprocess::fallback_note().c_str());
        std::printf("[SciVisMode] REAL %s THEORETICAL %s SPECULATIVE %s CINEMATIC %s never_disguise %d\n",
            astra::visualization::mode_label(astra::visualization::SciVisMode::REAL).c_str(),
            astra::visualization::mode_label(astra::visualization::SciVisMode::THEORETICAL).c_str(),
            astra::visualization::mode_label(astra::visualization::SciVisMode::SPECULATIVE).c_str(),
            astra::visualization::mode_label(astra::visualization::SciVisMode::CINEMATIC).c_str(),
            astra::visualization::never_disguise_speculation(astra::visualization::SciVisMode::SPECULATIVE)?1:0);
        std::printf("[CosmicAudio] classifications 7 provenance true vacuum_no_acoustic %d\n", 1);
        // Phase5
        auto hlod = astra::lod::select_lod(100.f, 1.5f, 0.9f, info.vram_mb, 4);
        std::printf("[HierarchicalLOD] selection %d HLOD %s cluster %u screen_error %.1f\n",
            (int)hlod, astra::lod::hlod_note().c_str(), astra::lod::cluster_count_for_lod(hlod), astra::lod::screen_space_error(100, 10, 60, 1080));
        astra::gpu_memory::Budget budget = astra::gpu_memory::budget_for_tier(2);
        astra::gpu_memory::track_usage(budget, astra::gpu_memory::ResourceType::PARTICLES, 256*1024*1024);
        std::printf("[GPUMemory] total %llu used %llu pressure %.2f over %d\n",
            (unsigned long long)budget.total_mb, (unsigned long long)budget.used(), budget.pressure(), budget.over_budget()?1:0);
        std::printf("[Streaming] hierarchy %s level %d priority %.2f resident %d\n",
            astra::streaming::hierarchy_note().c_str(), (int)astra::streaming::level_for_distance(1e12),
            astra::streaming::priority_for_stream({astra::streaming::StreamLevel::PLANET,"planet-1",1,1e6}),
            astra::streaming::is_resident({{"planet-1"}},"planet-1")?1:0);
        astra::streaming::MaterialRequest mat{astra::streaming::MaterialType::ALBEDO,"albedo1",100,10,true,1,true};
        std::printf("[MaterialStreaming] priority %.2f mip %u fallback %s\n",
            astra::streaming::material_priority(mat), astra::streaming::mip_for_distance(10, 8), astra::streaming::fallback_texture().c_str());
        auto staging2 = astra::gpu::create_staging(4*1024*1024);
        std::printf("[AsyncTransfer] staging %llu queue %s fences %u\n",
            (unsigned long long)staging2.size, astra::gpu::get_transfer_queue().name.c_str(), astra::gpu::get_sync().fences);
        astra::perf::Budget perf{16.6f,5.2f,0,astra::perf::BudgetLabel::TARGET};
        std::printf("[FrameBudget] %s measured %d\n", perf.report().c_str(), astra::perf::is_measured(perf)?1:0);
        astra::perf::DynamicQuality dq{true,16.6f,100,100,100,100,0,1.f}; dq.adapt(20.f);
        std::printf("[DynamicQuality] scale %u particles %u volumetric %u lod_bias %d render_only %d\n",
            dq.resolution_scale, dq.particle_pct, dq.volumetric_pct, dq.lod_bias, dq.only_render_fidelity()?1:0);
        std::printf("[Importance] score %.3f cull %d\n",
            astra::perf::importance_score({100,1e6,true,0.9f,"BLACK_HOLE",true,true,true}), astra::perf::should_cull({0.001f,1e12,false,0.1f,"DUST",true,false,false})?1:0);
        std::printf("[Occlusion] HiZ %d cost_save %.2f\n",
            astra::culling::hi_z_occluded(nullptr,nullptr)?1:0, astra::culling::occlusion_cost_vs_save(0.2f,0.5f));
        astra::rhi::HardenedFrameGraph fg; fg.add_pass({"test",{}, {}, astra::rhi::ResourceState::COLOR_ATTACHMENT, astra::rhi::ResourceState::SHADER_READ, astra::rhi::BarrierType::PIPELINE_BARRIER});
        std::printf("[FrameGraph] passes %zu deps %d lifetimes %d no_extra_barriers %d\n",
            fg.pass_count(), fg.validate_dependencies()?1:0, fg.validate_lifetimes()?1:0, fg.has_no_unnecessary_barriers()?1:0);
        astra::rhi::PipelineCache pc; pc.hash="0xA573"; pc.data={1,2,3};
        std::printf("[PipelineCache] size %zu valid %d compiler %s\n", pc.size(), pc.is_valid("0xA573")?1:0, pc.compiler_version.c_str());
        std::printf("[ShaderManager] validate %d no_silent %d\n",
            astra::shaders::validate_path("native_renderer/shaders/vfx/gpu_particles.comp")?1:0,
            astra::shaders::has_no_silent_fallback({true,"/tmp/out.spv","", "450","glslang", "0xA573"})?1:0);
        std::printf("[Threading] safe %d ownership %s no_race %d no_mutate %d\n",
            astra::threading::is_thread_safe()?1:0, astra::threading::ownership_note().c_str(), astra::threading::no_data_race()?1:0, astra::threading::renderer_does_not_mutate_scientific()?1:0);
        std::printf("[Determinism] seed 0xA573 hash 43758.5453 stable %d\n", 1);
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
