#pragma once
#include <string>
#include <vector>
#include <optional>
namespace astra::shaders {
struct ShaderSource {
    std::string path;
    std::string entry="main";
    bool is_compute=false;
    std::string permutation;
};
struct CompileResult {
    bool success=false;
    std::string spirv_path;
    std::string error;
    std::string version="450";
    std::string compiler="glslang 14.0";
    std::string hash;
};
CompileResult compile_glsl(const ShaderSource& src); // GLSL -> SPIR-V, no silent fallback
bool validate_path(const std::string& p); // prevents path traversal, validates asset path
bool has_no_silent_fallback(const CompileResult& r);
}
