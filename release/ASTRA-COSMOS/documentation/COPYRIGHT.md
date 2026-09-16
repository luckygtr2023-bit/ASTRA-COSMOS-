# COPYRIGHT

**Project:** ASTRA COSMOS

**Copyright:** Copyright © 2026 Lucky Kumar

**Author:** Lucky Kumar

**License for Original Work:** This project and its original source code, documentation, architecture, shaders, and original assets are protected by copyright to the extent permitted by applicable law. All rights reserved. No part of the original ASTRA COSMOS source may be reproduced or distributed without permission except as permitted by applicable law or explicit license.

Original work includes:
- ASTRA scientific engine (`astra/` — core, celestial, physics, motion, orbital, nbody, relativity, blackhole, spacetime, world, destruction, evolution, interaction, etc.)
- Native renderer (`native_renderer/src/` — RHI, scene, rendering systems, VFX, cinematic, performance, threading)
- Shaders (`native_renderer/shaders/` — GLSL, common.glsl astra_hash)
- Launcher (`native_renderer/launcher/launcher.cpp`)
- Product integration (`astra/product/supabase`, `supabase/migrations`)
- Documentation (`ASTRA_COSMOS_COMPLETE_PROJECT_SUMMARY.md`, `ASTRA_FINAL_RELEASE_AUDIT.md`, `README.md`, etc.)
- Build system (`native_renderer/CMakeLists.txt`, Ninja)

---

## THIRD-PARTY SOFTWARE AND CONTENT

Third-party libraries, dependencies, datasets, and assets remain subject to their respective licenses and retain their respective copyrights. No claim of ownership is made over third-party components.

| Component | License | Notes |
|-----------|---------|-------|
| Vulkan-Headers (`/home/user/Vulkan-Headers`) | Apache-2.0 / MIT (Khronos) | Header-only, not vendored in repo, used via include path |
| EnTT (`/home/user/entt`) | MIT | Header-only ECS, not vendored in repo source |
| Dear ImGui (`/home/user/imgui`) | MIT | UI library, not vendored in repo source |
| miniaudio (`/home/user/miniaudio/miniaudio.h`) | MIT / Public Domain (Unlicense) | Single-header audio |
| glslangValidator (`/tmp/glslangValidator`) | BSD-3-Clause (Khronos) | GLSL→SPIR-V compiler, external tool |
| Supabase (`supabase-py`, `supabase/migrations` using PostgreSQL) | Apache-2.0 / MIT | Auth/PostgreSQL/Storage/Realtime |
| PostgreSQL | PostgreSQL License | Database 15 |
| Python 3.11, CMake 3.28, Ninja | Various (PSF, Apache-2.0) | Build/runtime |
| Tracy (`src/profiling/tracy.cpp` source) | BSD-3-Clause | Profiler, integrated source |
| RenderDoc | MIT | GPU capture, NOT VERIFIED not installed |
| httpx, python-dotenv, pytest | MIT / BSD | Python dependencies |
| FastNoiseLite, meshoptimizer, KTX/basisu | Discussed but not found/vendored | NOT VERIFIED, not claimed |

Datasets where applicable (e.g., solar SOHO/GONG, pulsar Jodrell Bank) retain their original licenses and provenance is documented via `Provenance {object_id,dataset,transformation,license=CC0}` and `validate_label()`.

**Attribution:** All third-party components are attributed to their original owners. Their licenses govern their use. This COPYRIGHT file does not supersede those licenses.

---

*For licensing questions, contact Lucky Kumar.*
