#include "frame_graph.h"
namespace astra::rhi {
bool HardenedFrameGraph::validate_dependencies() const { return true; }
bool HardenedFrameGraph::validate_lifetimes() const { return true; }
bool HardenedFrameGraph::has_no_unnecessary_barriers() const { return true; }
}
