# Asset Licenses

| Asset | Category | Source | License | Usage | Modified |
|---|---|---|---|---|---|
| `assets/noise/perlin_512.png` (generated) | Noise | `procedural/noise_generator.py` (FastNoiseLite) | CC0 | Planet terrain / nebula density | Generated, not downloaded |
| `assets/stars/star_temperature_lut.png` (generated 16×256) | LUT | Generated from blackbody ramp (K → RGB) via `tools/generate_lut.py` | CC0 | Star color by temperature | Generated |
| `assets/skyboxes/milky_way_preview.hdr` (placeholder) | Skybox | Procedural starfield shader output baked to HDR | CC0 | Fallback skybox | Procedural |
| `assets/planets/earth_like_albedo.png` (512) | Planet | Procedural Voronoi + simplex via `procedural/planet_albedo.py` | CC0 | Example planet | Generated |
| `assets/particles/spark_32.png` | Particles | `vfx` spark texture (single white dot with falloff, self-made) | CC0 | Explosions/impacts | Created |
| `shaders/stars/procedural_starfield.gdshader` | Shader | Adapted from godotshaders.com MIT example (arcanewizard) | MIT (original), MIT (ASTRA mod) | Background | Adapted, exposure param added |
| `shaders/atmosphere/rayleigh_mie.gdshader` | Shader | Sean O'Neil approximations (public domain) + godotshaders MIT | MIT | Atmosphere | Simplified |
| `shaders/ocean/gerstner_ocean.gdshader` | Shader | godotshaders.com MIT ocean | MIT | Ocean | 4-wave |
| All other `shaders/*.gdshader` | Shader | ASTRA original | MIT | ASTRA | Original |
| `materials/*.tres` | Material | ASTRA original | MIT | ASTRA | Original |

No commercial textures, no CC-BY-SA without attribution, no Google Poly, no PolyHaven HDR (would require CC0 attribution — we chose procedural to avoid network download).

Verification: `tools/validate_assets.py` checks that `assets/` contains no binary blobs >2MB and every file has a counterpart in `ASSET_LICENSES.md`.
