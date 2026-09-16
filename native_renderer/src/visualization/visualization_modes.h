#pragma once
#include <string>
namespace astra::visualization {
enum class SciVisMode { REAL=0, THEORETICAL=1, SPECULATIVE=2, CINEMATIC=3 };
std::string mode_label(SciVisMode m);
std::string mode_watermark(SciVisMode m); // e.g., SPECULATIVE watermark 0.2
bool never_disguise_speculation(SciVisMode m); // must clearly identify
std::string example_for_mode(SciVisMode m); // Real observation, Theoretical wormhole, etc.
}
