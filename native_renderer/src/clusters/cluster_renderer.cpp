#include "cluster_renderer.h"
#include <cmath>
namespace astra::clusters {
std::vector<Galaxy> generate_cluster(uint64_t seed, int n, ClusterParams){
    std::vector<Galaxy> out; out.reserve(n);
    for(int i=0;i<n;i++){ Galaxy g; g.id="gal_"+std::to_string(seed+i); g.mass=1e42* std::sin(i*0.5+seed*1e-6); g.sfr= 1+ std::sin(i*0.3)*0.5; g.type = (i%3==0?"spiral":i%3==1?"elliptical":"irregular"); out.push_back(g); }
    return out;
}
double intracluster_density(double r){ return std::exp(-r*2.0) * (1+0.3*std::sin(r*20)); }
}
