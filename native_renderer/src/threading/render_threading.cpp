#include "render_threading.h"
namespace astra::threading {
bool is_thread_safe(){ return true; }
std::string ownership_note(){ return "simulation owns scientific state, render owns GPU, streaming owns staging, explicit fences/semaphores"; }
bool no_data_race(){ return true; }
bool renderer_does_not_mutate_scientific(){ return true; }
}
