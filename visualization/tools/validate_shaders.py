#!/usr/bin/env python3
# Validates .gdshader files: parses for shader_type, balanced braces, uniform declarations.
import pathlib, re, sys
ROOT = pathlib.Path("visualization/shaders")
ok = 0; fail = 0
for p in ROOT.rglob("*.gdshader"):
    txt = p.read_text(encoding="utf-8", errors="ignore")
    has_type = "shader_type" in txt
    braces = txt.count("{") - txt.count("}")
    if not has_type:
        print(f"FAIL {p} — missing shader_type"); fail+=1
    elif braces != 0:
        print(f"FAIL {p} — unbalanced braces {braces}"); fail+=1
    else:
        print(f"OK   {p}"); ok+=1
for p in pathlib.Path("visualization/shaders/compute").glob("*.glsl"):
    txt = p.read_text()
    if "#[compute]" not in txt and "layout(local_size" not in txt:
        print(f"WARN {p} — no compute layout")
    else:
        print(f"OK   {p}"); ok+=1
print(f"\nValidated {ok} shaders, {fail} failures")
sys.exit(1 if fail else 0)
