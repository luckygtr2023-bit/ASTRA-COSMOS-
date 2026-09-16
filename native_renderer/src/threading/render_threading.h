#pragma once
#include <string>
namespace astra::threading {
// Simulation thread, render thread, streaming thread, asset worker threads — explicit ownership, no data races
enum class ThreadType { SIMULATION, RENDER, STREAMING, ASSET_WORKER };
struct ThreadOwnership {
    ThreadType owner;
    bool is_simulation() const { return owner==ThreadType::SIMULATION; }
    bool can_mutate_scientific() const { return is_simulation(); }
};
bool is_thread_safe();
std::string ownership_note();
bool no_data_race();
bool renderer_does_not_mutate_scientific();
}
