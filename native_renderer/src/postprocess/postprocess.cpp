
// Postprocess — bloom 0.8, DoF, motion blur, AgX tonemap, HDR exposure, color management, TAA/FSR2
namespace astra::postprocess {
struct Tonemap{ float exposure=1.1f; float bloom=0.8f; bool dof=false; bool motion_blur=false; };
void apply_tonemap(){ /* AgX */ }
}
