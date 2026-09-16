
// Debug — Dear ImGui overlay, mirrors DiagnosticsOverlay CanvasLayer100
// Would show: sim_time, origin_offset, camera pos, renderer, FPS, draw_calls, classification counts
namespace astra::debug {
struct Overlay {
    bool enabled=true;
    void draw(float fps, float frame_ms, int objects, const char* renderer){
        (void)fps; (void)frame_ms; (void)objects; (void)renderer;
        // ImGui::Begin("ASTRA Diagnostics"); ImGui::Text("FPS %.1f", fps); ImGui::End();
    }
};
}
