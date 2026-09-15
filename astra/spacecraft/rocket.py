"""Rocket-equation helpers (Tsiolkovsky).

    delta_v = Isp * g0 * ln(m_initial / m_final)

Rearranged:
    m_final = m_initial * exp(-delta_v / (Isp * g0))
    propellant_needed = m_initial * (1 - exp(-delta_v / (Isp * g0)))

All functions validate inputs and raise InvalidRocketEquationError on
unphysical values (non-positive Isp, non-positive initial mass, m_final
greater than m_initial for a positive burn, etc.).
"""
from __future__ import annotations
import math

from astra.spacecraft.constants import G0, MIN_ISP, MAX_ISP
from astra.spacecraft.errors import InvalidRocketEquationError


def _validate_isp(isp: float) -> None:
    if not math.isfinite(isp) or isp <= 0.0:
        raise InvalidRocketEquationError(f"Isp must be positive finite, got {isp!r}")


def _validate_mass(m: float, name: str) -> None:
    if not (math.isfinite(m) and m > 0.0):
        raise InvalidRocketEquationError(
            f"{name} must be positive finite, got {m!r}"
        )


def rocket_delta_v(m_initial: float, m_final: float, isp: float) -> float:
    """delta_v = Isp * g0 * ln(m_initial / m_final)."""
    _validate_isp(isp)
    _validate_mass(m_initial, "m_initial")
    _validate_mass(m_final, "m_final")
    if m_final > m_initial:
        raise InvalidRocketEquationError(
            f"m_final ({m_final}) > m_initial ({m_initial}); "
            "rocket equation gives negative delta-v"
        )
    return isp * G0 * math.log(m_initial / m_final)


def propellant_for_delta_v(m_initial: float, delta_v: float, isp: float) -> float:
    """Propellant mass required to achieve delta_v from initial mass."""
    _validate_isp(isp)
    _validate_mass(m_initial, "m_initial")
    if not math.isfinite(delta_v) or delta_v < 0.0:
        raise InvalidRocketEquationError(
            f"delta_v must be non-negative finite, got {delta_v!r}"
        )
    m_final = m_initial * math.exp(-delta_v / (isp * G0))
    return m_initial - m_final


def mass_after_delta_v(m_initial: float, delta_v: float, isp: float) -> float:
    _validate_isp(isp)
    _validate_mass(m_initial, "m_initial")
    if not math.isfinite(delta_v) or delta_v < 0.0:
        raise InvalidRocketEquationError(
            f"delta_v must be non-negative finite, got {delta_v!r}"
        )
    return m_initial * math.exp(-delta_v / (isp * G0))


def remaining_delta_v(m_current: float, m_dry: float, isp: float) -> float:
    """Delta-v achievable by burning all remaining propellant.

    m_current : current total mass (dry + remaining propellant)
    m_dry     : dry mass
    isp       : specific impulse
    """
    _validate_isp(isp)
    _validate_mass(m_current, "m_current")
    if not (math.isfinite(m_dry) and m_dry > 0.0):
        raise InvalidRocketEquationError(
            f"m_dry must be positive finite, got {m_dry!r}"
        )
    if m_current < m_dry:
        raise InvalidRocketEquationError(
            f"m_current ({m_current}) < m_dry ({m_dry}); "
            "spacecraft has consumed more than its propellant"
        )
    if m_current == m_dry:
        return 0.0
    return isp * G0 * math.log(m_current / m_dry)
