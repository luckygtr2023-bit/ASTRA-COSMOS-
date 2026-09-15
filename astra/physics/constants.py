"""Physical constants and tolerance defaults for ASTRA Physics.

Units (SI-coherent, documented once here and relied on everywhere else)
-----------------------------------------------------------------------
length                  : metre          (m)
time                    : second         (s)
mass                    : kilogram       (kg)
velocity                : m/s
acceleration            : m/s^2
angular velocity        : rad/s
angular acceleration    : rad/s^2
force                   : newton         (N  = kg*m/s^2)
torque                  : newton-metre   (N*m)
momentum (linear)       : kg*m/s
angular momentum        : kg*m^2/s
impulse                 : N*s            (== kg*m/s)
energy                  : joule          (J  = N*m)
power                   : watt           (W  = J/s)
inertia (linear)        : kg*m^2
inertia (tensor)        : kg*m^2 per axis
gravitational parameter : m^3 / s^2      (GM)
gravitational constant  : m^3/(kg*s^2)   (G)

All ASTRA Physics interfaces use these units. No implicit conversions.
"""

# CODATA 2018 Newtonian constant of gravitation.
GRAVITATIONAL_CONSTANT: float = 6.67430e-11  # m^3 kg^-1 s^-2

# Default Plummer softening length. With softening eps > 0, the magnitude of
# the Newtonian force becomes F = G m1 m2 / (r^2 + eps^2) which is finite at
# r = 0. The value is deliberately small but non-zero; callers may override.
DEFAULT_SOFTENING: float = 1.0e-6  # metres

# Below this magnitude, a mass is treated as numerically zero for validation
# purposes (i.e. it is not a valid dynamical body). This is a *policy*
# threshold, not a physical cut-off.
DEFAULT_MASS_TOL: float = 1.0e-30  # kg
