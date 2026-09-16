#include "wormhole_whitehole.h"
#include <cmath>
namespace astra::wormhole {
double WarpParams::alcubierre_f(double r, double sigma, double R){ double v1 = sigma*(r+R); double v2 = sigma*(r-R); return (std::tanh(v1)-std::tanh(v2))/(2*std::tanh(sigma*R)); }
}
