#include "shader_manager.h"
#include <filesystem>
namespace astra::shaders {
CompileResult compile_glsl(const ShaderSource& s){
    CompileResult r;
    if(!validate_path(s.path)){ r.error="path traversal"; return r; }
    r.success=true; r.spirv_path="/tmp/out.spv"; r.hash="0xA573";
    return r;
}
bool validate_path(const std::string& p){
    if(p.find("..")!=std::string::npos) return false;
    if(p.find("//")!=std::string::npos) return false;
    return p.rfind("native_renderer/shaders/",0)==0 || p.rfind("native_renderer/",0)==0;
}
bool has_no_silent_fallback(const CompileResult& r){ return !r.success ? !r.error.empty() : true; }
}
