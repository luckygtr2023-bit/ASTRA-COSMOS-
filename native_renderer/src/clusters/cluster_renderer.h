#pragma once
#include <string>
#include <vector>
namespace astra::clusters {
struct Galaxy { std::string id; double mass=1e42; double sfr=1; std::string type="spiral"; };
struct ClusterParams { double mass=1e45; double temp_keV=5; double redshift=0.1; std::string status="SIMULATED"; };
std::vector<Galaxy> generate_cluster(uint64_t seed, int n, ClusterParams p);
double intracluster_density(double radius_norm);
}
