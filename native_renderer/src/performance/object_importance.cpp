#include "object_importance.h"
namespace astra::perf {
float importance_score(const ImportanceParams& p){
    if(!p.visible) return 0;
    float s = p.screen_size * (p.scientific_relevance+0.5f);
    if(p.focused) s*=3.f;
    if(p.user_target) s*=5.f;
    if(p.type=="BLACK_HOLE"||p.type=="STAR") s*=2.f;
    if(p.vfx_relevant) s*=1.5f;
    s /= (p.distance/1e6f + 1.f);
    if(s<0.01f && p.scientific_relevance>0.9f) s=0.01f; // important scientific objects not disappear
    return s;
}
bool should_cull(const ImportanceParams& p){ return importance_score(p) < 0.005f; }
}
