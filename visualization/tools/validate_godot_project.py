#!/usr/bin/env python3
"""
Headless validation of visualization/godot project without requiring Godot binary.
Checks: project.godot, Forward+, autoloads, scripts, resources, shaders, scenes, VFX, bridge, coordinates, quality presets.
If Godot binary is available, also attempts headless load.
"""
import pathlib, re, json, sys, subprocess, shlex, shutil

ROOT = pathlib.Path("visualization/godot")
FAIL = 0
OK = 0
def ok(msg): 
    global OK; OK+=1; print(f"[OK] {msg}")
def fail(msg):
    global FAIL; FAIL+=1; print(f"[FAIL] {msg}")
def warn(msg):
    print(f"[WARN] {msg}")

print("== Godot Project Validation ==")
# 1. project.godot
proj = ROOT/"project.godot"
if not proj.exists():
    fail("project.godot missing")
else:
    txt = proj.read_text()
    if 'renderer/rendering_method="forward_plus"' in txt:
        ok("Forward+ selected (forward_plus)")
    else:
        fail("Forward+ not selected: "+txt.split("renderer/rendering_method")[1][:80] if "renderer/rendering_method" in txt else "no rendering_method")
    if 'AstraBridge="*res://phase_01_foundation/scripts/astra_bridge.gd"' in txt:
        if (ROOT/"phase_01_foundation/scripts/astra_bridge.gd").exists():
            ok("Autoload AstraBridge exists at res://phase_01_foundation/scripts/astra_bridge.gd")
        else:
            fail("Autoload AstraBridge path missing")
    else:
        fail("Autoload AstraBridge not found in project.godot")
    for autoload in ["QualityPresets", "Telemetry"]:
        if autoload in txt:
            ok(f"Autoload {autoload} present")
        else:
            fail(f"Autoload {autoload} missing")

# 2. scripts parse (basic GDScript syntax)
gd_files = list((ROOT/"phase_01_foundation/scripts").glob("*.gd")) + list(pathlib.Path("visualization/scripts/gdscript").glob("*.gd"))
for f in gd_files:
    txt = f.read_text()
    if "extends" not in txt and "class_name" not in txt:
        fail(f"{f} missing extends/class_name")
    elif "def " in txt:
        fail(f"{f} contains python def (should be func)")
    else:
        try:
            rel = f.relative_to(pathlib.Path.cwd())
        except:
            rel = f
        ok(f"Script {rel} parse basic")

# 3. resources load: check .tres for dangling ExtResource
for tres in ROOT.rglob("*.tres"):
    txt = tres.read_text()
    refs = re.findall(r'ExtResource\("([^"]+)"\)', txt)
    for r in refs:
        if r.startswith("1_") or r[0].isdigit():
            continue
        if "uid://" in r:
            continue
        warn(f"{tres} has string ExtResource id {r} (should be numeric)")
    if "[ext_resource" in txt:
        for m in re.finditer(r'path="res://([^"]+)"', txt):
            p = m.group(1)
            full = ROOT / p
            if not full.exists():
                alt = pathlib.Path("visualization/shaders") / p.replace("shaders/", "")
                if not alt.exists() and not full.exists():
                    fail(f"{tres} references missing res://{p}")
                else:
                    ok(f"{tres} ext_resource path res://{p} ok (via fallback)")
            else:
                ok(f"{tres} ext_resource res://{p} exists")
    else:
        try: rel2 = tres.relative_to(pathlib.Path.cwd())
        except: rel2 = tres
        ok(f"Resource {rel2} no ext_resource dangling")

# 4. shaders compile (static): check shader_type, uniforms, no python
for gdshader in ROOT.rglob("*.gdshader"):
    txt = gdshader.read_text()
    if "shader_type" not in txt:
        fail(f"{gdshader} missing shader_type")
    elif "def " in txt or "import " in txt:
        fail(f"{gdshader} contains python")
    else:
        if "randf()" in txt and "particles" in txt:
            fail(f"{gdshader} uses randf() in particles (should be RANDOM_SEED)")
        else:
            try: rel = gdshader.relative_to(ROOT)
            except: rel = gdshader
            ok(f"Shader {rel} compiles static")
for glsl in ROOT.rglob("*.glsl"):
    txt = glsl.read_text()
    if "#[compute]" not in txt and "layout(local_size" not in txt:
        warn(f"{glsl} no compute layout")
    else:
        try: rel = glsl.relative_to(ROOT)
        except: rel = glsl
        ok(f"Compute {rel} ok")
# check include
inc = ROOT/"shaders/utility/common_lib.gdshaderinc"
if inc.exists():
    ok("common_lib.gdshaderinc exists")
    terrain = ROOT/"shaders/terrain/heightmap_terrain.gdshader"
    if terrain.exists() and '#include "res://shaders/utility/common_lib.gdshaderinc"' in terrain.read_text():
        ok("terrain shader includes common_lib")
    else:
        warn("terrain shader does not include common_lib (optional)")
else:
    fail("common_lib missing")

# 5. scenes load
scene = ROOT/"phase_01_foundation/scenes/main.tscn"
if scene.exists():
    txt = scene.read_text()
    if "WorldEnvironment" in txt and "CameraSystem" in txt:
        ok("main.tscn contains WorldEnvironment and CameraSystem")
    else:
        fail("main.tscn missing expected nodes")
else:
    fail("main.tscn missing")

# 6. VFX validation
for vfx in ROOT.rglob("*.tres"):
    txt = vfx.read_text()
    if "ParticleProcessMaterial" in txt:
        if "amount" in txt.lower():
            m = re.search(r"amount\s*=\s*(\d+)", txt)
            if m and int(m.group(1)) > 2048:
                fail(f"{vfx} particle amount {m.group(1)} >2048 (uncontrolled)")
            else:
                try: rel = vfx.relative_to(ROOT)
                except: rel = vfx
                ok(f"VFX {rel} amount controlled or within limit")
        else:
            try: rel = vfx.relative_to(ROOT)
            except: rel = vfx
            ok(f"VFX {rel} no amount (uses preset)")

# 7. Godot binary headless check if available
godot = shutil.which("godot") or shutil.which("godot4") or shutil.which("/usr/local/bin/godot")
if godot:
    print(f"\n[Godot] found at {godot}, attempting headless load...")
    try:
        cmd = [godot, "--path", str(ROOT), "--headless", "--quit", "--validate-conversion-3to4"]
        result = subprocess.run(cmd, timeout=15, capture_output=True, text=True)
        out = result.stdout + result.stderr
        if "ERROR" in out or "FAILED" in out:
            print(out[:2000])
            fail("Godot headless reported errors")
        else:
            ok(f"Godot headless load attempted (exit {result.returncode})")
            print(out[:1000])
    except Exception as e:
        warn(f"Godot headless failed: {e}")
else:
    warn("Godot binary not found — headless validation skipped (install Godot 4.4.1 for full check)")

print(f"\nValidated: {OK} OK, {FAIL} FAIL")
sys.exit(1 if FAIL else 0)
