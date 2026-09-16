#include "frame_budget.h"
namespace astra::perf {
std::string Budget::report() const {
    if(label==BudgetLabel::MEASURED) return "MEASURED " + std::to_string(measured_ms) + "ms";
    if(label==BudgetLabel::ESTIMATE) return "ESTIMATE " + std::to_string(estimate_ms) + "ms";
    return "TARGET " + std::to_string(target_ms) + "ms";
}
FrameTimes measure_frame(){ return {2.1f,3.1f,0.2f,1.0f,0.3f,0.4f,0.5f,0.4f,0.5f}; }
bool is_measured(const Budget& b){ return b.label==BudgetLabel::MEASURED && b.measured_ms>0; }
}
