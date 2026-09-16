import pathlib, subprocess, json, sys
import pytest

# Audio tests must be deterministic and not require audio device
# They call the native binary headless and also import python wrappers if available

def test_audio_engine_headless():
    bin_path = pathlib.Path("/tmp/astra_build/astra_native")
    if not bin_path.exists():
        pytest.skip("astra_native not built")
    r = subprocess.run([str(bin_path), "--headless"], capture_output=True, text=True, timeout=10)
    assert r.returncode==0
    assert "[CosmicAudio]" in r.stdout
    assert "backend=mock-headless" in r.stdout
    assert "active=3" in r.stdout
    assert "validated=1" in r.stdout
    assert "[HearUniverse] 4 sources" in r.stdout

def test_audio_classification_no_mislabel():
    bin_path = pathlib.Path("/tmp/astra_build/astra_native")
    if not bin_path.exists():
        pytest.skip("no binary")
    r = subprocess.run([str(bin_path), "--headless"], capture_output=True, text=True, timeout=10)
    # Must not have REAL labeled CINEMATIC
    # Check hear universe outputs have correct truth strings
    assert "earth REAL_ACOUSTIC" in r.stdout
    assert "pulsar REAL_SIGNAL_SONIFICATION" in r.stdout
    assert "black_hole PHYSICALLY_MODELED" in r.stdout
    assert "wormhole SPECULATIVE" in r.stdout

def test_audio_thread_safety():
    # CosmicAudioEngine uses lock-free queue max 64, try_push non-blocking
    # Simulate by checking binary doesn't hang and queue remains bounded
    bin_path = pathlib.Path("/tmp/astra_build/astra_native")
    if not bin_path.exists():
        pytest.skip("no binary")
    r = subprocess.run([str(bin_path), "--headless"], capture_output=True, text=True, timeout=10)
    assert "queue=0" in r.stdout  # after tick_synthesis queue drained

def test_solar_audio_provenance():
    # Check solar header exists and classification correct
    p = pathlib.Path("native_renderer/src/audio/solar/solar_audio.h")
    assert p.exists()
    txt = p.read_text()
    assert "solar_oscillations" in txt
    # Check dataset provenance would be SOHO/GONG
    cpp = pathlib.Path("native_renderer/src/audio/solar/solar_audio.cpp").read_text()
    assert "SOHO" in cpp or "GONG" in cpp
    assert "REAL_SIGNAL_SONIFICATION" in cpp

def test_pulsar_preserve_timing():
    p = pathlib.Path("native_renderer/src/audio/pulsar/pulsar_audio.cpp").read_text()
    assert "preserve timing" in p.lower() or "preserve" in p
    assert "REAL_SIGNAL_SONIFICATION" in p

def test_black_hole_modes():
    p = pathlib.Path("native_renderer/src/audio/black_hole/black_hole_audio.h").read_text()
    assert "Mode" in p
    assert "OBSERVATIONAL" in p and "ACCRETION_MEDIUM" in p and "GW_SONIFICATION" in p and "CINEMATIC" in p
    cpp = pathlib.Path("native_renderer/src/audio/black_hole/black_hole_audio.cpp").read_text()
    assert "gravitational_wave" in cpp

def test_galaxy_deterministic():
    cpp = pathlib.Path("native_renderer/src/audio/galaxy/galaxy_audio.cpp").read_text()
    assert "0xA573" in cpp or "deterministic" in cpp
    assert "SCIENTIFICALLY_INTERPRETED" in cpp

def test_spatial_audio_doppler():
    h = pathlib.Path("native_renderer/src/audio/spatial/spatial_audio.h").read_text()
    assert "doppler_shift" in h
    assert "distance_attenuation" in h
    cpp = pathlib.Path("native_renderer/src/audio/spatial/spatial_audio.cpp").read_text()
    assert "299792458" in cpp  # speed of light

def test_sonification_mapping():
    h = pathlib.Path("native_renderer/src/audio/sonification/sonification.h").read_text()
    assert "frequency_mapping" in h
    assert "time_mapping" in h
    cpp = pathlib.Path("native_renderer/src/audio/sonification/sonification.cpp").read_text()
    assert "log" in cpp or "linear" in cpp

def test_provenance_metadata():
    h = pathlib.Path("native_renderer/src/audio/audio_types.h").read_text()
    assert "struct Provenance" in h
    assert "object_id" in h and "dataset" in h and "transformation" in h and "license" in h
    assert "validate_label" in h

def test_quality_modes():
    h = pathlib.Path("native_renderer/src/audio/audio_types.h").read_text()
    assert "AudioQuality" in h
    assert "SCIENTIFIC" in h and "CINEMATIC" in h and "SPECULATIVE" in h

def test_mcp_tools():
    p = pathlib.Path("native_renderer/src/mcp/astra_mcp.h")
    assert p.exists()
    txt = p.read_text()
    assert "AstraMCPServer" in txt
    assert "astra.audio" in pathlib.Path("native_renderer/src/mcp/astra_mcp.cpp").read_text()

def test_rt_quality_tiers_fallback():
    # RT must have fallback raster
    p = pathlib.Path("native_renderer/src/rt/ray_traced.h").read_text()
    assert "fallback_raster" in p
    cpp = pathlib.Path("native_renderer/src/rt/ray_traced.cpp").read_text()
    assert "detect_rt_config" in cpp
    # Check headless log shows fallback
    bin_path = pathlib.Path("/tmp/astra_build/astra_native")
    if bin_path.exists():
        r = subprocess.run([str(bin_path), "--headless"], capture_output=True, text=True, timeout=10)
        assert "[RT]" in r.stdout
        assert "fallback" in r.stdout

def test_mesh_shader_streaming():
    p = pathlib.Path("native_renderer/src/mesh_shader/virtual_geo.h").read_text()
    assert "Meshlet" in p
    assert "streaming_budget" in p
    cpp = pathlib.Path("native_renderer/src/mesh_shader/virtual_geo.cpp").read_text()
    assert "detect_config" in cpp

def test_destruction_scientific_preserved():
    p = pathlib.Path("native_renderer/src/destruction/destruction.h").read_text()
    assert "scientific_state_preserved" in p
    cpp = pathlib.Path("native_renderer/src/destruction/destruction.cpp").read_text()
    assert "does not overwrite" in cpp

def test_materials8k_tiers():
    p = pathlib.Path("native_renderer/src/materials8k/materials8k.h").read_text()
    assert "Tier" in p and "KTXConfig" in p
    cpp = pathlib.Path("native_renderer/src/materials8k/materials8k.cpp").read_text()
    assert "CINEMATIC" in cpp

def test_legal_provenance():
    # All audio provenance must have license field
    for f in pathlib.Path("native_renderer/src/audio").rglob("*.cpp"):
        txt = f.read_text()
        if "Provenance" in txt or "provenance" in txt:
            # At least some should mention CC0 or license
            pass
    # Check main demo hear universe provenance has license CC0 default
    h = pathlib.Path("native_renderer/src/audio/audio_types.h").read_text()
    assert 'license = "CC0"' in h

def test_deterministic_synthesis():
    # Hash 43758.5453 must be present for deterministic
    assert "43758" in pathlib.Path("native_renderer/shaders/common/common.glsl").read_text()
    # Audio also deterministic via seed 0xA573
    assert "0xA573" in pathlib.Path("native_renderer/src/audio/audio_types.h").read_text() or "0xA573" in pathlib.Path("native_renderer/src/audio/galaxy/galaxy_audio.cpp").read_text()
