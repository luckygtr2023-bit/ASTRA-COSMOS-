#pragma once
#include <string>
#include <vector>
namespace astra::streaming {
// Hierarchical streaming: Universe → Galaxy → StarSystem → PlanetarySystem → Planet → Region → TerrainTile → LocalObject
enum class StreamLevel { UNIVERSE=0, GALAXY=1, STAR_SYSTEM=2, PLANETARY_SYSTEM=3, PLANET=4, REGION=5, TERRAIN_TILE=6, LOCAL_OBJECT=7 };
struct StreamRequest {
    StreamLevel level;
    std::string id;
    float priority=1.f;
    float distance=0;
};
struct StreamState {
    std::vector<std::string> resident;
    size_t count() const { return resident.size(); }
    std::string top() const { return resident.empty()?"none":resident.back(); }
};
StreamLevel level_for_distance(double dist);
float priority_for_stream(const StreamRequest& r); // screen size, distance, visibility, importance, focus
bool is_resident(const StreamState& s, const std::string& id);
std::string hierarchy_note();
}
