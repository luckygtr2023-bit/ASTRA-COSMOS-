#!/usr/bin/env python3
# Generates star_temperature_lut.png (16x256, CC0) — blackbody approx
try:
    from PIL import Image
    has_pil=True
except ImportError:
    has_pil=False
import math, pathlib
W, H = 256, 16
out = pathlib.Path("visualization/assets/stars/star_temperature_lut.png")
out.parent.mkdir(parents=True, exist_ok=True)
if has_pil:
    im = Image.new("RGB", (W,H))
    for x in range(W):
        t = x/(W-1)
        # blackbody approx (2000→40000K)
        r = min(1.0, 1.0 - math.pow(max(t-0.15,0)/0.85,0.6) *0.5 if t>0.2 else 1.0)
        g = pow(t,0.45)
        b = pow(t*1.05,0.75)
        col = (int(r*255), int(g*255), int(b*255))
        for y in range(H):
            im.putpixel((x,y), col)
    im.save(out)
    print(f"generated {out} with Pillow")
else:
    # PPM fallback
    out_ppm = out.with_suffix(".ppm")
    with open(out_ppm,"w") as f:
        f.write(f"P3\n{W} {H}\n255\n")
        for y in range(H):
            for x in range(W):
                t = x/(W-1)
                r = min(1.0, 1.0 - pow(max(t-0.15,0)/0.85,0.6)*0.5 if t>0.2 else 1.0)
                g = pow(t,0.45)
                b = pow(t*1.05,0.75)
                f.write(f"{int(r*255)} {int(g*255)} {int(b*255)} ")
            f.write("\n")
    print(f"generated {out_ppm} (Pillow not available)")
