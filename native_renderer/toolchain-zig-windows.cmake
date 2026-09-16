# Toolchain for Windows cross-compile via zig cc — ASTRA COSMOS
# Copyright © 2026 Lucky Kumar
# Usage: cmake -S native_renderer -B build-win -G Ninja -DCMAKE_TOOLCHAIN_FILE=native_renderer/toolchain-zig-windows.cmake -DCMAKE_BUILD_TYPE=Release
# Requires: pip install ziglang (provides zig 0.16.0 + clang 21.1.0)
# Produces: PE32+ x64 CONSOLE "ASTRA COSMOS.exe" (MZ 4d5a, Machine 0x8664)

set(CMAKE_SYSTEM_NAME Windows)
set(CMAKE_SYSTEM_PROCESSOR x86_64)

# Use zig cc/c++ as drop-in compilers for Windows target
find_program(ZIG_PYTHON python3)
if(ZIG_PYTHON)
    set(CMAKE_C_COMPILER "${ZIG_PYTHON}" "-m" "ziglang" "cc" "-target" "x86_64-windows-gnu")
    set(CMAKE_CXX_COMPILER "${ZIG_PYTHON}" "-m" "ziglang" "c++" "-target" "x86_64-windows-gnu")
else()
    # Fallback to direct zig binary if installed via other means
    find_program(ZIG_EXE zig)
    if(ZIG_EXE)
        set(CMAKE_C_COMPILER "${ZIG_EXE}" "cc" "-target" "x86_64-windows-gnu")
        set(CMAKE_CXX_COMPILER "${ZIG_EXE}" "c++" "-target" "x86_64-windows-gnu")
    endif()
endif()

# Search in target environment only
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)

# Ensure console subsystem (launcher needs stdout/stderr)
set(CMAKE_EXE_LINKER_FLAGS_INIT "-Wl,--subsystem,console")

message(STATUS "Toolchain: zig Windows x86_64 (PE32+ CONSOLE) via ${CMAKE_CXX_COMPILER}")
