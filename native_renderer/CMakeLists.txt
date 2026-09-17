cmake_minimum_required(VERSION 3.28)
project(ASTRA_NativeRenderer VERSION 0.1.0 LANGUAGES CXX C)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Options
option(ASTRA_ENABLE_VULKAN "Enable Vulkan 1.3 backend" ON)
option(ASTRA_ENABLE_VALIDATION "Enable Vulkan validation layers" ON)
option(ASTRA_ENABLE_TRACY "Enable Tracy profiler" OFF)
option(ASTRA_BUILD_TESTS "Build tests" ON)
option(ASTRA_BUILD_TOOLS "Build tools" ON)

# Dependencies discovery (header-only fallbacks where possible)
find_package(Vulkan QUIET)
if(NOT Vulkan_FOUND)
    message(WARNING "Vulkan SDK not found via find_package — using /home/user/Vulkan-Headers headers. Install libvulkan-dev for full build.")
    set(Vulkan_INCLUDE_DIR "/home/user/Vulkan-Headers/include")
endif()

# GLFW / SDL3 — try pkg-config, else header-only fallback note
find_package(PkgConfig QUIET)
if(PKG_CONFIG_FOUND)
    pkg_check_modules(GLFW glfw3)
    pkg_check_modules(SDL3 sdl3)
endif()

# EnTT — header-only, cloned to /home/user/entt
if(EXISTS "/home/user/entt/src/entt/entt.hpp")
    set(ENTT_INCLUDE_DIR "/home/user/entt/src")
else()
    message(STATUS "EnTT not found at /home/user/entt — will use minimal internal ECS fallback")
endif()

# Dear ImGui — cloned to /home/user/imgui
if(EXISTS "/home/user/imgui/imgui.h")
    set(IMGUI_DIR "/home/user/imgui")
endif()

# Miniaudio — header-only MIT single header
if(EXISTS "/home/user/miniaudio/miniaudio.h")
    set(MINIAUDIO_INCLUDE_DIR "/home/user/miniaudio")
    message(STATUS "miniaudio: ${MINIAUDIO_INCLUDE_DIR}")
endif()

# GLSLANG — prefer system, else /home/user/glslang
if(EXISTS "/home/user/glslang/CMakeLists.txt")
    set(GLSLANG_DIR "/home/user/glslang")
endif()

# Compiler flags for AAA quality: strict, Werror-ish, optimization
if(MSVC)
    # Windows bootstrap builds the existing native target, not the legacy launcher.
    add_compile_options(/W4 /utf-8 /permissive-)
else()
    add_compile_options(-Wall -Wextra -Wpedantic -Wconversion -Wshadow)
    if(CMAKE_BUILD_TYPE STREQUAL "Release")
        add_compile_options(-O3 -march=native -flto)
        add_link_options(-flto)
    else()
        add_compile_options(-O1 -g -DDEBUG)
    endif()
endif()

# Core library: astra_renderer
file(GLOB_RECURSE RENDERER_SOURCES
    src/*.cpp
)

add_library(astra_renderer STATIC ${RENDERER_SOURCES})
find_package(Threads REQUIRED)

target_include_directories(astra_renderer PUBLIC
    src
    src/rhi
    ${Vulkan_INCLUDE_DIR}
    ${ENTT_INCLUDE_DIR}
    ${IMGUI_DIR}
    ${MINIAUDIO_INCLUDE_DIR}
)

if(GLFW_FOUND)
    target_include_directories(astra_renderer PUBLIC ${GLFW_INCLUDE_DIRS})
    target_link_libraries(astra_renderer PUBLIC ${GLFW_LIBRARIES})
endif()

target_compile_definitions(astra_renderer PUBLIC
    ASTRA_VERSION_MAJOR=0 ASTRA_VERSION_MINOR=1 ASTRA_VERSION_PATCH=0
    $<$<BOOL:${ASTRA_ENABLE_VALIDATION}>:ASTRA_VALIDATION>
)

# Legacy launcher source retained for opt-in developer builds; START.bat is primary.
option(ASTRA_BUILD_LAUNCHER "Build legacy Windows launcher ASTRA COSMOS.exe" OFF)
if(ASTRA_BUILD_LAUNCHER)
    add_executable(astra_launcher launcher/launcher.cpp)
    # Output name with space — Windows launcher: "ASTRA COSMOS.exe"
    set_target_properties(astra_launcher PROPERTIES
        OUTPUT_NAME "ASTRA COSMOS"
        SUFFIX ".exe"
        CXX_STANDARD 20
        CXX_STANDARD_REQUIRED ON
    )
    find_package(Threads REQUIRED)
    target_link_libraries(astra_launcher PRIVATE Threads::Threads)
    # On Windows, avoid console? Keep console for logs (stdout/stderr preserved)
    if(MSVC)
        target_compile_options(astra_launcher PRIVATE /O2 /GL)
        set_target_properties(astra_launcher PROPERTIES LINK_FLAGS "/LTCG /SUBSYSTEM:CONSOLE")
    else()
        target_compile_options(astra_launcher PRIVATE -O3)
    endif()
    # Install launcher to release root
    install(TARGETS astra_launcher RUNTIME DESTINATION .)
    message(STATUS "Launcher: ASTRA COSMOS.exe from launcher/launcher.cpp")
endif()

# Main executable — headless + windowed (production entry point, invoked by launcher)
add_executable(astra_native
    src/main.cpp
)
target_link_libraries(astra_native PRIVATE astra_renderer Threads::Threads)
# Also link renderer threads
target_link_libraries(astra_renderer PUBLIC Threads::Threads)

# Tools
if(ASTRA_BUILD_TOOLS)
    add_subdirectory(tools EXCLUDE_FROM_ALL)
endif()

# Tests
if(ASTRA_BUILD_TESTS)
    enable_testing()
    add_subdirectory(tests EXCLUDE_FROM_ALL)
endif()

# Shader compilation — glslangValidator if available
find_program(GLSLANG_VALIDATOR glslangValidator PATHS /tmp /tmp/glslang_build2/StandAlone /usr/bin NO_DEFAULT_PATH)
find_program(GLSLANG_VALIDATOR_FALLBACK glslangValidator)
if(GLSLANG_VALIDATOR OR GLSLANG_VALIDATOR_FALLBACK)
    if(NOT GLSLANG_VALIDATOR)
        set(GLSLANG_VALIDATOR ${GLSLANG_VALIDATOR_FALLBACK})
    endif()
    message(STATUS "glslangValidator: ${GLSLANG_VALIDATOR}")
    file(GLOB_RECURSE GLSL_SHADERS shaders/*.glsl shaders/*.vert shaders/*.frag shaders/*.comp)
    foreach(SHADER ${GLSL_SHADERS})
        get_filename_component(SHADER_NAME ${SHADER} NAME)
        add_custom_command(OUTPUT ${CMAKE_BINARY_DIR}/shaders/${SHADER_NAME}.spv
            COMMAND ${CMAKE_COMMAND} -E make_directory ${CMAKE_BINARY_DIR}/shaders
            COMMAND ${GLSLANG_VALIDATOR} -V ${SHADER} -o ${CMAKE_BINARY_DIR}/shaders/${SHADER_NAME}.spv
            DEPENDS ${SHADER}
            COMMENT "Compiling ${SHADER_NAME} -> SPIR-V"
        )
    endforeach()
else()
    message(WARNING "glslangValidator not found — shader SPIR-V compilation will be validated by tools/validate_shaders.py (static)")
endif()

# Install
install(TARGETS astra_renderer astra_native
    ARCHIVE DESTINATION lib
    LIBRARY DESTINATION lib
    RUNTIME DESTINATION bin
)
install(DIRECTORY shaders DESTINATION share/astra/shaders)
install(DIRECTORY assets DESTINATION share/astra/assets)

message(STATUS "ASTRA Native Renderer — C++20 Vulkan 1.3")
message(STATUS "  Build type: ${CMAKE_BUILD_TYPE}")
message(STATUS "  Vulkan: ${Vulkan_FOUND} ${Vulkan_INCLUDE_DIR}")
message(STATUS "  GLFW: ${GLFW_FOUND}")
message(STATUS "  EnTT: ${ENTT_INCLUDE_DIR}")
message(STATUS "  Tests: ${ASTRA_BUILD_TESTS} Tools: ${ASTRA_BUILD_TOOLS}")
