"""Constants shim for graphics material library.

Provides GRAVITATIONAL_CONSTANT and SPEED_OF_LIGHT for imports like
`from config.constants import ...` while delegating to the authoritative
astra.mathematics.constants.
"""

try:
    from astra.mathematics.constants import GRAVITATIONAL_CONSTANT, SPEED_OF_LIGHT
except Exception:
    # Fallback values (SI units)
    GRAVITATIONAL_CONSTANT = 6.67430e-11
    SPEED_OF_LIGHT = 299792458.0

__all__ = ["GRAVITATIONAL_CONSTANT", "SPEED_OF_LIGHT"]
