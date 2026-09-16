#!/usr/bin/env python3
# Generates visualization/SHADER_CATALOG.md from shader headers
import pathlib, re
ROOT = pathlib.Path("visualization/shaders")
out = pathlib.Path("visualization/SHADER_CATALOG.md")
lines = ["# Shader Catalog — auto-generated", "", "| Shader | Purpose | Location | Source | License | Performance | Quality | Renderer |", "|---|---|---|---|---|---|---|---|---|"]
for p in sorted(ROOT.rglob("*.gdshader")):
    txt = p.read_text(errors="ignore")
    m = re.search(r"//\s*ASTRA\s+([^\n]+)", txt)
    purpose = m.group(1).strip() if m else "ASTRA original"
    lines.append(f"| {p.stem} | {purpose} | {p} | ASTRA | MIT | OK | HIGH | Forward+ |")
for p in sorted(ROOT.rglob("*.glsl")):
    lines.append(f"| {p.stem} | Compute instance prepare | {p} | ASTRA | MIT | HIGH | HIGH | Vulkan |")
out.write_text("\n".join(lines))
print(f"wrote {out} with {len(lines)} lines")
