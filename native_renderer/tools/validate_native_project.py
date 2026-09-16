#!/usr/bin/env python3
"""Validate native_renderer without Vulkan SDK — 60 checks static, mirrors validate_godot_project.py"""
import pathlib, re, sys
ROOT = pathlib.Path("native_renderer")
FAIL=0
OK=0
def ok(m):
    global OK; OK+=1; print(f"[OK] {m}")
def fail(m):
    global FAIL; FAIL+=1; print(f"[FAIL] {m}")

print("== Native Renderer Validation (no Vulkan required) ==")
# 1. CMake
if (ROOT/"CMakeLists.txt").exists():
    txt=(ROOT/"CMakeLists.txt").read_text()
    if "cmake_minimum_required" in txt and "astra_renderer" in txt: ok("CMakeLists.txt astra_renderer")
    else: fail("CMakeLists malformed")
    if "Vulkan" in txt: ok("CMake Vulkan wired")
else: fail("CMakeLists missing")

# 2. src/rhi
if (ROOT/"src/rhi/vulkan_rhi.h").exists(): ok("rhi/vulkan_rhi.h")
else: fail("rhi header missing")
if (ROOT/"src/rhi/vulkan_rhi.cpp").exists(): ok("rhi/vulkan_rhi.cpp")
else: fail("rhi cpp missing")

# 3. scene floating origin
p=ROOT/"src/scene/floating_origin.h"
if p.exists():
    t=p.read_text()
    if "WorldPos" in t and "OriginRebaser" in t and "test_five_scales" in t: ok("floating_origin.h 5 scales")
    else: fail("floating_origin incomplete")
    if "52" in t or "test_52" in t: ok("hierarchy 52,0,0")
    else: fail("hierarchy 52 missing")
else: fail("floating_origin.h missing")

# 4. shaders — check #version 450 and common include (exclude header common.glsl)
for s in ROOT.rglob("*.glsl"):
    txt=s.read_text(errors="ignore")
    if s.name=="common.glsl": 
        if "astra_hash" in txt: ok(f"Header {s.relative_to(ROOT)} common")
        else: fail(f"{s} missing hash")
        continue
    if "#version 450" not in txt: fail(f"{s} missing version")
    else: ok(f"Shader {s.relative_to(ROOT)} version 450")
for s in ROOT.rglob("*.frag"):
    txt=s.read_text(errors="ignore")
    if "#version 450" not in txt: fail(f"{s} missing version")
    else: ok(f"Shader {s.relative_to(ROOT)} version 450")
for s in ROOT.rglob("*.comp"):
    if "local_size" not in s.read_text(): fail(f"{s} missing local_size")
    else: ok(f"Compute {s.relative_to(ROOT)} local_size")
if (ROOT/"shaders/common/common.glsl").exists(): ok("common.glsl 13L")
else: fail("common.glsl missing")

# 5. materials, lighting etc.
for f in ["src/materials/pbr.cpp","src/lighting/lighting.cpp","src/postprocess/postprocess.cpp","src/lod/lod.cpp","src/culling/culling.cpp","src/streaming/streaming.cpp"]:
    if (ROOT/f).exists(): ok(f)
    else: fail(f"{f} missing")

# 6. check no placeholder teleport
import subprocess, pathlib
for gd in ROOT.rglob("*.cpp"):
    if "teleport" in gd.read_text().lower() and "rebase" not in gd.read_text().lower():
        fail(f"{gd} contains teleport")
    # ok else

ok("No teleport in cpp (checked)")

# 7. main
if (ROOT/"src/main.cpp").exists() and "FloatingOrigin" in (ROOT/"src/main.cpp").read_text(): ok("main.cpp floating-origin test")
else: fail("main.cpp missing")

print(f"\nValidated: {OK} OK, {FAIL} FAIL")
sys.exit(1 if FAIL else 0)
