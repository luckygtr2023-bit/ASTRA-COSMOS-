# Addons — Curated

No binary addons are bundled in this delivery to keep supply chain minimal.

Evaluated addons (see DEPENDENCIES.md):
- Phantom Camera (MIT, 4.4) — inspiration for `camera_system.gd`, not bundled (reimplemented minimal)
- Terrain3D — rejected (GPL, heavy)
- Gaea — rejected (editor-only)

If you need an addon:
1. Verify Godot 4.4 compat, last commit <6 months, MIT/Apache2
2. Run `tools/verify_third_party.py` (hash, grep for http/eval/OS.execute)
3. Place under `visualization/addons/<name>/` with `SOURCE.md` + `LICENSE`
4. Document in `DEPENDENCIES.md` and `THIRD_PARTY.md`
