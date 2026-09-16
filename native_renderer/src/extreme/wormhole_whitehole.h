#pragma once
#include <string>
namespace astra::wormhole {
struct WormholeParams { double b0=2.0; std::string status="THEORETICAL"; };
struct WhiteHoleParams { double mass=1e30; std::string status="THEORETICAL / SPECULATIVE"; };
struct WarpParams { double sigma=8, radius=4; std::string status="SPECULATIVE"; double alcubierre_f(double r, double sigma, double R); };
}
