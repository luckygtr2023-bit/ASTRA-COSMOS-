#pragma once
#include <string>
namespace astra::perf {
struct ImportanceParams {
    float screen_size=0;
    float distance=1e9f;
    bool focused=false;
    float scientific_relevance=0.5f; // 0-1
    std::string type="STAR";
    bool visible=true;
    bool vfx_relevant=false;
    bool user_target=false;
};
float importance_score(const ImportanceParams& p); // unified score, important objects not disappear when small
bool should_cull(const ImportanceParams& p);
}
