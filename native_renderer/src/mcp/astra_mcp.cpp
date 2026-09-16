
#include "astra_mcp.h"
#include <algorithm>
namespace astra::mcp {
std::string AstraMCPServer::call(const std::string& n, const std::string& a){ for(auto& t: tools_) if(t.name==n) return t.fn(a); return "unknown tool "+n; }
std::vector<std::string> AstraMCPServer::list_tools() const { std::vector<std::string> o; for(auto& t: tools_) o.push_back(t.name); return o; }
void AstraMCPServer::init_default_tools(){
 register_tool({"astra.bridge.poll","Poll RenderState hash",[](auto a){ return "bridge hash 42"; }});
 register_tool({"astra.shader.compile","Compile GLSL->SPIR-V",[](auto a){ return "glslangValidator -V "+a; }});
 register_tool({"astra.benchmark.run","Run benchmark Phase01",[](auto a){ return "benchmark 5.2ms"; }});
 register_tool({"astra.audio.sonify","Sonify dataset",[](auto a){ return "sonified "+a; }});
 register_tool({"astra.audio.hear_universe","Hear the Universe mode",[](auto a){ return "hear "+a; }});
 register_tool({"astra.asset.bake_lut","Bake star LUT",[](auto a){ return "baked 16x256"; }});
}
}
