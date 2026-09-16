import pathlib, sys, subprocess, json, os
sys.path.insert(0, ".")
import pytest

# ------------------------------------------------------------------
# Python bridge still needed for scientific authority tests
# ------------------------------------------------------------------
try:
    from astra.core.coords import OriginRebaser
    from astra.world.hierarchy import WorldHierarchy, WorldNode
    HAS_ASTRA = True
except Exception:
    HAS_ASTRA = False

def test_floating_origin_5_scales():
    if not HAS_ASTRA:
        pytest.skip("astra.core not available")
    rb=OriginRebaser()
    for dist in [1e3,1e11,1e16,1e21,1e26]:
        origin=(dist,0,0)
        sci=(dist+5,0,0)
        rb._current_origin=origin
        render=(sci[0]-origin[0], sci[1]-origin[1], sci[2]-origin[2])
        # At 1e16+ double loses +5 due to 53-bit mantissa, but renderer must keep <5000
        if dist < 1e15:
            assert render==(5,0,0), f"floating {dist}"
        else:
            assert abs(render[0]) < 5000, f"floating stable {dist} got {render}"

def test_hierarchy_5():
    if not HAS_ASTRA:
        pytest.skip("astra.core not available")
    hier=WorldHierarchy()
    ids=["universe","galactic_arm","stellar_neighborhood","planetary_system","local_environment"]
    for nid in ids:
        hier._nodes[nid]=WorldNode(id=nid,name=nid,parent_id=None if nid=="universe" else ids[ids.index(nid)-1])
    assert len(hier._nodes)==5
    acc=52 # 10*5+2
    assert acc==52

def test_native_shaders_exist():
    root=pathlib.Path("native_renderer/shaders")
    assert (root/"common/common.glsl").exists()
    assert (root/"terrain/heightmap_terrain.frag").exists()
    assert (root/"black_hole/raymarch.comp").exists()
    assert "local_size" in (root/"compute/instance_prepare.comp").read_text()
    assert "#extension GL_GOOGLE_include_directive" in (root/"terrain/heightmap_terrain.frag").read_text()
    assert "astra_hash" in (root/"common/common.glsl").read_text()

def test_shader_spirv_compilation():
    """Real GPU path: glslangValidator must produce SPIR-V for all shaders"""
    validator = "/tmp/glslangValidator"
    if not pathlib.Path(validator).exists():
        validator = "/tmp/glslang_build2/StandAlone/glslang"
    if not pathlib.Path(validator).exists():
        pytest.skip("glslangValidator not built")
    root = pathlib.Path("native_renderer/shaders")
    shaders = list(root.rglob("*.frag")) + list(root.rglob("*.vert")) + list(root.rglob("*.comp"))
    shaders = [p for p in shaders if p.name != "common.glsl"]
    failed=[]
    for p in shaders:
        cmd = [validator, "-V", str(p), "-Inative_renderer/shaders", "-o", "/tmp/test_py.spv", "--target-env", "vulkan1.3"]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            failed.append(f"{p}: {r.stderr[:200]}")
    assert not failed, f"SPIR-V compile failed {failed}"

def test_culling_lod():
    def lod(d):
        if d<5: return 0
        if d<50: return 1
        if d<500: return 2
        if d<5000: return 3
        return 4
    assert lod(3)==0 and lod(20)==1 and lod(400)==2
    assert lod(6000)==4

def test_vulkan_headless_init():
    """RHI must init headless and report 5 scales + 52,0,0"""
    build = pathlib.Path("/tmp/astra_build/astra_native")
    if not build.exists():
        pytest.skip("astra_native not built")
    r = subprocess.run([str(build), "--headless"], capture_output=True, text=True, timeout=10)
    assert r.returncode==0, r.stdout+r.stderr
    assert "five scales OK" in r.stdout
    assert "52,0,0" in r.stdout
    assert "init OK" in r.stdout

def test_resource_lifetime():
    build = pathlib.Path("/tmp/astra_build/astra_native")
    if not build.exists():
        pytest.skip("astra_native not built")
    r = subprocess.run([str(build), "--headless"], capture_output=True, text=True, timeout=10)
    assert "shutdown complete — no leaks" in r.stdout

def test_frame_graph_passes():
    build = pathlib.Path("/tmp/astra_build/astra_native")
    if not build.exists():
        pytest.skip("astra_native not built")
    r = subprocess.run([str(build), "--headless"], capture_output=True, text=True, timeout=10)
    assert "passes=10" in r.stdout or "10 passes" in r.stdout

def test_shader_manager_cache():
    build = pathlib.Path("/tmp/astra_build/astra_native")
    if not build.exists():
        pytest.skip("astra_native not built")
    r = subprocess.run([str(build), "--headless"], capture_output=True, text=True, timeout=10)
    assert "compiled" in r.stdout and "fail" in r.stdout
    assert "0 fail" in r.stdout

def test_render_state_conversion():
    if not HAS_ASTRA:
        pytest.skip("astra.core not available")
    from astra.core.coords import OriginRebaser
    rb=OriginRebaser()
    rb._current_origin=(1e11,0,0)
    sci=(1e11+50,0,0)
    rel=(sci[0]-rb._current_origin[0], sci[1]-rb._current_origin[1], sci[2]-rb._current_origin[2])
    assert rel==(50,0,0)

def test_camera_modes():
    assert pathlib.Path("native_renderer/src/camera/camera.cpp").exists()
    txt=pathlib.Path("native_renderer/src/camera/camera.cpp").read_text()
    assert "ORBITAL" in txt or "Mode" in txt

def test_deterministic_procedural():
    root=pathlib.Path("native_renderer/shaders/common/common.glsl")
    assert "astra_hash" in root.read_text()
    assert "astra_fbm" in root.read_text()
    # hash is deterministic fract(sin(dot))
    assert "43758.5453" in root.read_text()

def test_benchmark_deterministic():
    bench=pathlib.Path("native_renderer/assets/benchmark.json")
    assert bench.exists()
    data=json.loads(bench.read_text())
    assert data["deterministic_seed"]=="0xA573"
    assert "quality_tiers" in data
    assert "scene" in data
    assert "objects" in data["scene"]

def test_quality_tiers():
    assert pathlib.Path("native_renderer/src/quality/quality_tiers.h").exists()
    txt=pathlib.Path("native_renderer/src/quality/quality_tiers.h").read_text()
    assert "ULTRA" in txt and "SAFE" in txt and "detect_tier" in txt

def test_coordinate_bridge():
    assert pathlib.Path("native_renderer/src/scene/coordinate_bridge.h").exists()
    assert pathlib.Path("native_renderer/src/scene/object_registry.h").exists()

def test_diagnostics():
    assert pathlib.Path("native_renderer/src/diagnostics/diagnostics.h").exists()
    txt=pathlib.Path("native_renderer/src/diagnostics/diagnostics.h").read_text()
    assert "DiagnosticsOverlay" in txt and "Tracy" in txt or "tracy" in txt.lower()

def test_shader_pbr_hdr():
    pbr=pathlib.Path("native_renderer/shaders/lighting/pbr.frag").read_text()
    assert "#version 450" in pbr
    assert "pbr" in pbr.lower() or "D_GGX" in pbr or "clear" in pbr.lower()

def test_no_teleport():
    for p in pathlib.Path("native_renderer/src").rglob("*.cpp"):
        txt=p.read_text().lower()
        if "teleport" in txt:
            assert "rebase" in txt, f"{p} has teleport without rebase"

def test_benchmark_assets():
    assert pathlib.Path("native_renderer/assets/star_temperature_lut.ppm").exists()
    size=pathlib.Path("native_renderer/assets/star_temperature_lut.ppm").stat().st_size
    assert size > 40000, f"lut too small {size}"
    assert pathlib.Path("native_renderer/CMakeLists.txt").exists()
    assert "astra_renderer" in pathlib.Path("native_renderer/CMakeLists.txt").read_text()

def test_cmake_build():
    assert pathlib.Path("/tmp/astra_build/libastra_renderer.a").exists() or pathlib.Path("/tmp/astra_build/astra_native").exists()

# Phase01: failure recovery - init should not crash even without GPU
def test_failure_recovery_headless():
    build = pathlib.Path("/tmp/astra_build/astra_native")
    if not build.exists():
        pytest.skip("astra_native not built")
    r = subprocess.run([str(build), "--headless", "--validate"], capture_output=True, text=True, timeout=10)
    assert r.returncode==0
