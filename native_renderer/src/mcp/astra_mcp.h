
#pragma once
#include <string>
#include <vector>
#include <functional>
namespace astra::mcp {
struct Tool { std::string name; std::string description; std::function<std::string(const std::string&)> fn; };
class AstraMCPServer {
public:
    void register_tool(const Tool& t){ tools_.push_back(t); }
    std::string call(const std::string& name, const std::string& args);
    std::vector<std::string> list_tools() const;
    void init_default_tools(); // asset, shader, benchmark, audio
private:
    std::vector<Tool> tools_;
};
}
