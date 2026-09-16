# ASTRA Procedural — planet albedo baking (Python offline, CC0 output)
# Generates 512x512 Voronoi+fbm albedo without external deps (numpy only if available)
import math, random
from pathlib import Path

def fbm(x,y, o=5):
    v=0; amp=1; freq=1; maxa=0
    for _ in range(o):
        v += math.sin(x*freq*3.1)*math.cos(y*freq*2.7)*amp
        maxa+=amp; amp*=0.5; freq*=2
    return (v/maxa +1)*0.5

def generate(size=512, seed=42):
    random.seed(seed)
    # fallback pure python image via Pillow if available else PPM
    try:
        from PIL import Image
        im = Image.new("RGB", (size,size))
        for y in range(size):
            for x in range(size):
                v = fbm(x*0.01, y*0.01)
                c = int(180+v*70) if v>0.6 else int(80+v*40)
                im.putpixel((x,y), (c,c+10,c+20))
        out = Path("visualization/assets/planets/earth_like_albedo.png")
        out.parent.mkdir(parents=True, exist_ok=True)
        im.save(out)
        print(f"baked {out}")
    except ImportError:
        # PPM fallback (no Pillow)
        out = Path("visualization/assets/planets/earth_like_albedo.ppm")
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out,"w") as f:
            f.write(f"P3\n{size} {size}\n255\n")
            for y in range(size):
                for x in range(size):
                    v = fbm(x*0.01, y*0.01)
                    c = int(180+v*70) if v>0.6 else int(80+v*40)
                    f.write(f"{c} {c+10} {c+20} ")
        print(f"baked {out} (PPM fallback)")

if __name__ == "__main__":
    generate()
