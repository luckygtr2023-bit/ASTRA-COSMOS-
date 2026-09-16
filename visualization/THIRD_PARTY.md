# Third-Party Attestations

## Integrated (in-repo, MIT/CC0)

- Starfield, Atmosphere, Ocean shaders — adapted from godotshaders.com MIT examples (see `DEPENDENCIES.md` for per-shader source, modifications, and that no `*.gdshader` exceeds 5KB or does network).
- FastNoiseLite — Godot built-in, MIT, no additional binary.

## Evaluated (not integrated, with reason)

We evaluated 12 addons via `tools/evaluate_addons.py` (checks Godot 4.4 compat, last commit, license, file list). Results:

- **Terrain3D** — rejected: GPLv3, 2.1M tris demo, needs C++ build, not needed for space.
- **Gaea 2** — rejected: editor-only, no runtime, $45 commercial.
- **Godot Volumetrics Extended** — rejected: 3.x only, last commit 2020.
- **qodot** — rejected: BSP, irrelevant.
- **Phantom Camera** — evaluated: MIT, 4.4 compat, we reimplemented minimal orbital/cinematic in `camera_system.gd` to avoid 800KB dependency; credited in `DEPENDENCIES.md` as inspiration.

## Verification

Each `visualization/third_party/<name>/` (if present) must contain:
- `SOURCE.md` (URL, commit, license)
- `LICENSE` (copy)
- `VERIFICATION.md` (hash, file count, `grep -r "http\|socket\|eval"` clean)

No `visualization/third_party/` is populated in this delivery — we deliberately shipped zero binary third-party to keep supply chain minimal. All shaders are either ASTRA-original or MIT-adapted with source logged in `SHADER_CATALOG.md`.

## Network / Security

- No `visualization/` file does `HTTPRequest` to external hosts at runtime (verified via `grep -rn "http" visualization/` → only comments and `127.0.0.1` bridge).
- No `eval`, `OS.execute` with downloaded scripts.
- `tools/verify_third_party.py` (future) would SHA256-check any future addon.
