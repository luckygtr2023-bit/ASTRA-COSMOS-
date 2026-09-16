#!/usr/bin/env python3
import pathlib
ROOT = pathlib.Path("visualization/assets")
MAX_MB = 2
fail=0
for p in ROOT.rglob("*"):
    if p.is_file():
        mb = p.stat().st_size/1024/1024
        if mb > MAX_MB:
            print(f"FAIL {p} {mb:.1f}MB > {MAX_MB}MB"); fail+=1
        else:
            print(f"OK {p} {mb:.2f}MB")
print("asset validation", "FAILED" if fail else "PASSED")
raise SystemExit(1 if fail else 0)
