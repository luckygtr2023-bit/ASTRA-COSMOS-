# ASTRA COSMOS — Windows Executable Diagnosis

**Date:** 2026-09-17  
**File:** `ASTRA COSMOS.exe` (space in name, `.exe` extension)  
**Branch:** `arena/01a0a5a2-astra-cosmos`

## Summary

Original (2026-09-16) was Linux ELF64 named `.exe` — Windows loader rejects with `ERROR_BAD_EXE_FORMAT` → "This app can't run on your PC". Repaired 2026-09-17 via `zig cc 0.16.0` to valid PE32+ x64 Console. Launcher source `native_renderer/launcher/launcher.cpp` (258 lines) already cross-platform; only toolchain changed. No placeholder.

## 17 Attributes

| # | Attribute | Before (ELF) | After (PE) | How Verified |
|---|-----------|--------------|------------|--------------|
| 1 | Exact filename | `ASTRA COSMOS.exe` | `ASTRA COSMOS.exe` | `ls -lb "ASTRA COSMOS.exe"` |
| 2 | Extension | `.exe` | `.exe` | `ls` |
| 3 | Size | 46136 (45K) | 945152 (923K) | `stat -c %s`, `ls -lh` |
| 4 | File type | ELF64 LSB pie executable, x86-64, dynamically linked | PE32+ executable (console) x86-64 | `od -An -tx1 -N4` |
| 5 | Binary format | ELF magic `7f 45 4c 46 02 01 01 00` | PE magic `4d 5a 78 00` MZ at 0 | `od` |
| 6 | Valid PE | NO (ELF) | YES `PE\0\0` at e_lfanew 0x78, OptMagic 0x20b | `python struct` e_lfanew + PE sig |
| 7 | Architecture | X86-64 | X86-64 Machine 0x8664 | `readelf -h` / `struct Mach` |
| 8 | OS target | UNIX System V, INTERP /lib64/ld-linux-x86-64.so.2 | Windows | `readelf -l` vs PE |
| 9 | Compiler/toolchain | GCC 12.2.0 (Debian 12.2.0-14) native `g++` | zig 0.16.0 (clang 21.1.0) `x86_64-windows-gnu` via `pip install ziglang` | `g++ --version`, `python3 -m ziglang version` |
| 10 | Build config | Release -O3 -flto (CMake) | -O2 -std=c++20 (zig) | `CMakeLists.txt` |
| 11 | Subsystem | N/A (ELF) | CONSOLE 3 | `struct opt[68:70]` |
| 12 | Entry point | 0x4d20 (ELF) | RVA 0xa350 (PE) | `readelf -h` / `struct opt[16:20]` |
| 13 | Dependencies | `ld-linux-x86-64.so.2` `libstdc++.so` `libgcc_s` | `KERNEL32.dll` `api-ms-win-crt-*.dll` | `readelf -l` / `strings` |
| 14 | Corruption | NO — 13 PHDR, 32 sections, valid | NO — 7 sections, valid | `readelf -l`, `struct` |
| 15 | Is Linux ELF | YES | NO | `od` |
| 16 | Is x86/x64/ARM | x64 | x64 (0x8664, not 0x14c x86 nor 0xaa64 ARM64) | `Machine` |
| 17 | Matches target (Windows x64 console) | NO | YES | `Machine 0x8664` + `PE32+` + `Subsystem CONSOLE` |

## 15 Diagnosis Fields

| Field | Before | After |
|-------|--------|-------|
| Filename | ASTRA COSMOS.exe | ASTRA COSMOS.exe |
| Size | 46136 | 945152 |
| File type | ELF64 | PE32+ |
| Valid PE | NO | YES |
| Architecture | X86-64 | X86-64 0x8664 |
| OS target | Linux | Windows |
| Compiler | GCC 12.2.0 | zig 0.16.0 clang 21.1.0 |
| Subsystem | — | CONSOLE 3 |
| Entry | 0x4d20 | 0xa350 |
| Dependencies | ld-linux | KERNEL32.dll |
| Corrupted | NO | NO |
| Is ELF | YES | NO |
| x64 | YES | YES |
| Matches target | NO | YES |
| Likely cause | Linux binary named .exe via `g++` not Windows compiler | REPAIRED via zig `x86_64-windows-gnu` |

## Likely Cause & Evidence

**Cause:** CMake `add_executable(astra_launcher ...)` `OUTPUT_NAME "ASTRA COSMOS" SUFFIX ".exe"` built with default Linux `g++` (no Windows toolchain) → ELF `7f45` output misnamed `.exe`. Windows loader expects MZ (`4d5a`) at 0, reads `e_lfanew` at 0x3c, expects `PE\0\0` (`50 45 00 00`) and `Machine 0x8664`; gets ELF header → `ERROR_BAD_EXE_FORMAT` (193) → user sees "This app can't run on your PC. To find a version for your PC, check with the software publisher."

**Evidence:**

```
# Before
$ od -An -tx1 -N4 "ASTRA COSMOS.exe"      # → 7f 45 4c 46 (ELF) not 4d 5a (MZ)
$ readelf -h "ASTRA COSMOS.exe"           # → Class: ELF64, OS/ABI: UNIX - System V, Machine: Advanced Micro Devices X86-64, Type: DYN
$ readelf -l "ASTRA COSMOS.exe"           # → INTERP /lib64/ld-linux-x86-64.so.2, Type: DYN, 13 PHDR, 32 sections, Entry 0x4d20
$ objdump -f "ASTRA COSMOS.exe"           # → file format elf64-x86-64, architecture i386:x86-64, HAS_SYMS DYNAMIC D_PAGED
$ stat -c %s "ASTRA COSMOS.exe"           # → 46136

# After (repaired)
$ od -An -tx1 -N4 "ASTRA COSMOS.exe"      # → 4d 5a 78 00 (MZ)
$ python3 -c "import struct; d=open('ASTRA COSMOS.exe','rb').read(); e=struct.unpack('<I',d[0x3c:0x40])[0]; print(hex(e), d[e:e+4])" # → 0x78 b'PE\x00\x00'
$ python3 -c "import struct; d=open('ASTRA COSMOS.exe','rb').read(); e=struct.unpack('<I',d[0x3c:0x40])[0]; print(hex(struct.unpack('<H',d[e+4:e+6])[0]))" # → 0x8664 (x64)
$ python3 -c "import struct; d=open('ASTRA COSMOS.exe','rb').read(); e=struct.unpack('<I',d[0x3c:0x40])[0]; print(hex(struct.unpack('<H',d[e+24:e+24+2])[0]))" # → 0x20b (PE32+)
$ strings "ASTRA COSMOS.exe" | grep KERNEL32 # → KERNEL32.dll
```

**Valid Windows PE expected:** `MZ` at 0, `e_lfanew` → `PE\0\0`, `Machine 0x8664`, `OptMagic 0x20b` (PE32+), `Subsystem CONSOLE (3)`, imports `KERNEL32.dll` — **now true after repair.**

## Repair Performed (Minimum)

**Goal:** Windows x64 PE32+ `Machine 0x8664` `Subsystem CONSOLE` preserving real production launcher (not placeholder).

**Toolchain:** `pip install ziglang --break-system-packages` → `zig 0.16.0` (clang 21.1.0) provides `x86_64-windows-gnu` without apt/root. Verified when `apt` blocked (`deb.debian.org Connection failed`, `/var/lib/apt/lists/partial` missing, `mingw-w64` not found, `curl https://ziglang.org` SSL_ERROR_SYSCALL).

**Commands (from repo root):**
```bash
pip install ziglang --break-system-packages
python3 -m ziglang c++ -target x86_64-windows-gnu -O2 -std=c++20 -o /tmp/launcher_win.exe native_renderer/launcher/launcher.cpp
# verify
od -An -tx1 -N4 /tmp/launcher_win.exe  # 4d 5a 78 00
python3 <<'PY'
import struct
d=open('/tmp/launcher_win.exe','rb').read()
e=struct.unpack('<I',d[0x3c:0x40])[0]
print(hex(e), d[e:e+4], hex(struct.unpack('<H',d[e+4:e+6])[0]), hex(struct.unpack('<H',d[e+24:e+24+2])[0]), struct.unpack('<H',d[e+24+68:e+24+70])[0])
# → 0x78 b'PE\x00\x00' 0x8664 0x20b 3
PY
cp /tmp/launcher_win.exe "ASTRA COSMOS.exe"
cp /tmp/launcher_win.exe "release/ASTRA-COSMOS/ASTRA COSMOS.exe"
```

**CMake integration (alternative):**
```bash
cmake -S native_renderer -B /tmp/win -G Ninja -DCMAKE_TOOLCHAIN_FILE=native_renderer/toolchain-zig-windows.cmake -DCMAKE_BUILD_TYPE=Release
cmake --build /tmp/win -j2  # → PE "ASTRA COSMOS.exe"
```
See `native_renderer/toolchain-zig-windows.cmake`.

**Preserved:** `src/main.cpp` real entry (`astra_native`), launcher 258 lines, `GetModuleFileNameA`/`CreateProcessA` vs `/proc/self/exe`/`fork+execv`, space handling, headless forwarding, validation. No demo headless-only.

**Honesty:** Size 945K vs 46K because Windows static links C++ stdlib/filesystem (vs Linux dynamic libstdc++). `strip`/`objcopy --strip-all` for PE via GNU fails (`invalid elf file`); size expected.

## Post-Repair Validation (11 Checks)

| # | Check | Expected | Result | Note |
|---|-------|----------|--------|------|
| 1 | File exists | PE exists | PASS 945152 | `ls -lh` |
| 2 | Valid PE | MZ PE\0\0 | PASS 4d5a 78 00 PE | `od`/`struct` |
| 3 | Correct arch | x64 0x8664 | PASS | `Machine` |
| 4 | Dependencies | KERNEL32.dll | PASS | `strings` |
| 5 | Subsystem | CONSOLE | PASS 3 | `opt` |
| 6 | Starts | `.\ASTRA COSMOS.exe --help` | PARTIALLY — PE cannot exec on Linux (`Exec format error` expected); Linux ELF logic verified via `/tmp/astra_build/ASTRA COSMOS.exe --headless` (23/23) | Windows manual |
| 7 | Production launches | → astra_native + 23 shaders | PARTIALLY — launcher checks `astra_native` and `astra_native.exe`; Linux verified, Windows needs `astra_native.exe` PE (currently Linux ELF 161K at `release/bin/astra_native`) | `launcher.cpp: nativeCandidates` |
| 8 | Not mock | Real launcher | PASS 258 lines | `wc -l` |
| 9 | Exit codes | 0/1 | PASS | `launcher.cpp` |
| 10 | Startup errors | Missing files | PASS | `launcher.cpp` |
| 11 | Renderer/Vulkan | Mock vs RTX | MOCK PASS (RTX 4090 Mock 23/23 52,0,0 10 passes), REAL GPU NOT VERIFIED (no vulkaninfo/libvulkan.so/SDK) | `astra_native --headless` |

**Windows manual verification:**
```powershell
.\ASTRA` COSMOS.exe --help      # launcher help + RHI init
.\ASTRA` COSMOS.exe --headless
# expect MZ, Machine 0x8664, PE32+, Subsystem CONSOLE, KERNEL32.dll
```

## Remaining Limitations

- `astra_native` (full renderer) remains Linux ELF 161K at `release/bin/astra_native`; Windows `astra_native.exe` PE not yet built (requires Vulkan SDK, EnTT, full CMake with zig — heavier, not blocked but not done in this repair which targeted launcher per TASK B).
- REAL GPU not verified (mock only) — `Vulkan SDK not found — using /home/user/Vulkan-Headers`, no `vulkaninfo`/`renderdoccmd`/`tracy-server`.
- No `strip` for PE size reduction via GNU; 923K is static-linked size.
- Performance `5.2 ms HIGH estimate_ms` is target not measured.

## Files Changed

- `ASTRA COSMOS.exe` : ELF 46K → PE 923K (MZ 4d5a, PE32+, x64, CONSOLE)
- `release/ASTRA-COSMOS/ASTRA COSMOS.exe` : same
- `native_renderer/toolchain-zig-windows.cmake` : new
- `README.md` : updated §§15,17,18,19,20,22
- `EXECUTABLE_DIAGNOSIS.md` : new (this file)

## Commands & Tests

```bash
pip install ziglang --break-system-packages
python3 -m ziglang c++ -target x86_64-windows-gnu -O2 -std=c++20 -o /tmp/launcher_win.exe native_renderer/launcher/launcher.cpp
cp /tmp/launcher_win.exe "ASTRA COSMOS.exe"
cp /tmp/launcher_win.exe "release/ASTRA-COSMOS/ASTRA COSMOS.exe"
python3 -m pytest native_renderer/tests/ -q  # 89 passed, 2 skipped
python3 native_renderer/tools/validate_native_project.py  # 221 OK
/tmp/astra_build/astra_native --headless  # 23/23, 52,0,0, 10 passes, no leaks
/tmp/astra_build/"ASTRA COSMOS.exe" --headless  # Linux ELF launcher, same
od -An -tx1 -N4 "ASTRA COSMOS.exe"  # 4d 5a 78 00
```
