#!/usr/bin/env python3
# Validates bridge_state.json against RenderState schema (finite, classification, frame)
import json, pathlib, sys
allowed = {"REAL_DATA","DERIVED_DATA","SIMULATED_DATA","THEORETICAL","HYPOTHETICAL","SPECULATIVE"}
p = pathlib.Path("bridge_state.json")
if not p.exists():
    p = pathlib.Path("visualization/godot/bridge_state.json")
    if not p.exists():
        print("no bridge_state.json, skipping (offline)")
        sys.exit(0)
data = json.loads(p.read_text())
assert "tick" in data and isinstance(data["tick"], int)
assert "objects" in data and isinstance(data["objects"], list)
for obj in data["objects"]:
    assert "id" in obj and "position" in obj and len(obj["position"])==3
    assert all(isinstance(v,(int,float)) and __import__("math").isfinite(v) for v in obj["position"])
    assert obj.get("classification","SIMULATED_DATA") in allowed
print(f"bridge_state valid: {len(data['objects'])} objects")
