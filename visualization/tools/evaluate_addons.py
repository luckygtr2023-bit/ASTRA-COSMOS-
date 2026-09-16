#!/usr/bin/env python3
# Evaluates Godot addons for compatibility, activity, license
import pathlib, re
candidates = [
    ("Terrain3D", "https://github.com/TokisanGames/Terrain3D", "GPL"),
    ("Phantom Camera", "https://github.com/ramokz/phantom-camera", "MIT"),
    ("Gaea", "https://github.com/BenjaTK/Gaea", "MIT"),
]
print("Addon evaluation:")
for name, url, lic in candidates:
    print(f"- {name}: {url} ({lic}) — {'REJECT: GPL' if lic=='GPL' else 'OK MIT, reimplement minimal'}")
print("See visualization/DEPENDENCIES.md for decisions")
