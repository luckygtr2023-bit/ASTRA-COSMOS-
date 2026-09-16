"""ASTRA COSMOS - Special Relativity core utilities.

Contract: robust, deterministic numerics for Lorentz factors and the
v < c speed limit of massive objects.

Integration with existing ASTRA systems:
    - Accepts a classical ``astra.mathematics.Vector3`` velocity (m/s) OR a
      plain float magnitude everywhere, so relativistic quantities interoperate
      seamlessly with ``astra.motion`` / ``astra.physics`` states.
    - ``kinetic_energy`` converges to ``astra.physics.energy.kinetic_energy``
      (K = 1/2 m |v|^2) in the v -> 0 limit.
    - ``relativistic_momentum`` converges to ``astra.physics.momentum.linear_momentum``
      (p = m v) in the v -> 0 limit.

Units: SI-coherent (m, s, kg, J). c is exact in SI by definition.
Determinism: pure functions of the inputs; no RNG, no wall-clock, no globals.
"""

from __future__ import annotations

import math
from typing import Union

from astra.mathematics import Vector3
from astra.relativity.exceptions import (
    InvalidRestMassError,
    InvalidVelocityError,
    LightSpeedViolation,
)

# Exact by definition in the International System of Units (CODATA 2018).
SPEED_OF_LIGHT: float = 299792458.0  # m/s
C_SQUARED: float = SPEED_OF_LIGHT * SPEED_OF_LIGHT  # m^2 / s^2

# Below this beta the Taylor expansion gamma ~ 1 + b^2/2 + 3 b^4/8 is used.
# (The closed form 1/sqrt(1-b^2) is already smooth here, but expanding first
# also makes (gamma - 1) cancellation-free for kinetic energy at tiny v.)
LOW_BETA_TAYLOR_THRESHOLD: float = 1.0e-5

# A velocity input is either a magnitude in m/s or a classical Vector3.
SpeedInput = Union[float, Vector3]


def speed(v: SpeedInput) -> float:
    """Return the speed in m/s from a float magnitude or a Vector3 velocity.

    The sign of a float magnitude is irrelevant (all formulas use beta^2),
    but the input must be finite.
    """
    if isinstance(v, Vector3):
        s = v.magnitude()
    else:
        s = float(v)
    if math.isnan(s) or math.isinf(s):
        raise InvalidVelocityError(f"Velocity cannot be NaN or Infinite, got {v!r}")
    return s


def beta(v_mag: SpeedInput) -> float:
    """Calculate beta = v / c in [0, inf) from a magnitude or Vector3."""
    return speed(v_mag) / SPEED_OF_LIGHT


def lorentz_factor(v_mag: SpeedInput) -> float:
    """Calculate the Lorentz factor gamma = (1 - beta^2)^(-1/2).

    Handles the low-speed regime with a Taylor expansion
    ``gamma ~ 1 + 0.5 beta^2 + 0.375 beta^4`` (for ``beta < 1e-5``) so that
    derived quantities such as ``gamma - 1`` stay precise for v -> 0.

    Raises:
        InvalidVelocityError: if the speed is NaN or infinite.
        LightSpeedViolation: if the speed >= c (massive-object hard limit).
    """
    b = beta(v_mag)

    if b >= 1.0:
        raise LightSpeedViolation(
            f"Velocity {speed(v_mag)} >= c ({SPEED_OF_LIGHT} m/s) for massive object."
        )

    # Low-speed Taylor expansion: gamma = 1 + 0.5 b^2 + 0.375 b^4 + O(b^6)
    if b < LOW_BETA_TAYLOR_THRESHOLD:
        b2 = b * b
        return 1.0 + 0.5 * b2 + 0.375 * (b2 * b2)

    return 1.0 / math.sqrt(1.0 - b * b)


def _validate_rest_mass(rest_mass: float) -> float:
    """Validate a rest mass (finite, non-negative). Returns it unchanged."""
    m = float(rest_mass)
    if math.isnan(m) or math.isinf(m) or m < 0.0:
        raise InvalidRestMassError(f"Rest mass must be finite and >= 0, got {rest_mass!r}")
    return m


def relativistic_mass(rest_mass: float, v_mag: SpeedInput) -> float:
    """Calculate the relativistic mass gamma * m0 (kg).

    Note: "relativistic mass" is retained as a legacy ASTRA API name; it is
    exactly gamma * m0 and equals the rest mass when v = 0.
    """
    m0 = _validate_rest_mass(rest_mass)
    return m0 * lorentz_factor(v_mag)


def total_energy(rest_mass: float, v_mag: SpeedInput) -> float:
    """Calculate the total energy E = gamma * m0 * c^2 (J).

    At v = 0 this reduces to the rest energy m0 * c^2.
    """
    return relativistic_mass(rest_mass, v_mag) * C_SQUARED


def _gamma_minus_one(v_mag: SpeedInput) -> float:
    """Compute ``gamma - 1`` without catastrophic cancellation.

    For beta below LOW_BETA_TAYLOR_THRESHOLD the series
    ``gamma - 1 = 0.5 b^2 + 0.375 b^4`` is evaluated *directly* (never via
    ``lorentz_factor(...) - 1``), so kinetic energy stays exact down to
    v = 0 instead of collapsing to 0 J through float cancellation.

    Raises:
        LightSpeedViolation: if the speed >= c (massive-object hard limit).
    """
    b = beta(v_mag)

    if b >= 1.0:
        raise LightSpeedViolation(
            f"Velocity {speed(v_mag)} >= c ({SPEED_OF_LIGHT} m/s) for massive object."
        )

    if b < LOW_BETA_TAYLOR_THRESHOLD:
        b2 = b * b
        return 0.5 * b2 + 0.375 * (b2 * b2)

    return 1.0 / math.sqrt(1.0 - b * b) - 1.0


def kinetic_energy(rest_mass: float, v_mag: SpeedInput) -> float:
    """Calculate the relativistic kinetic energy Ek = (gamma - 1) * m0 * c^2 (J).

    Converges to the classical ``astra.physics.energy.kinetic_energy``
    (1/2 m v^2) as v -> 0; uses the cancellation-free ``gamma - 1`` series
    so the classical limit is recovered to full double precision.
    """
    m0 = _validate_rest_mass(rest_mass)
    return _gamma_minus_one(v_mag) * m0 * C_SQUARED


def relativistic_momentum(mass: float, velocity: Vector3) -> Vector3:
    """Calculate the relativistic 3-momentum p = gamma * m0 * v (kg*m/s).

    Mirrors ``astra.physics.momentum.linear_momentum`` (p = m v) and converges
    to it as v -> 0. Raises LightSpeedViolation if |v| >= c.
    """
    m0 = _validate_rest_mass(mass)
    gamma = lorentz_factor(velocity)
    return velocity * (gamma * m0)


def kinetic_energy_v(rest_mass: float, velocity: Vector3) -> float:
    """Vector3-based kinetic energy: ``kinetic_energy(m0, |velocity|)`` (J)."""
    return kinetic_energy(rest_mass, speed(velocity))


def total_energy_v(rest_mass: float, velocity: Vector3) -> float:
    """Vector3-based total energy: ``total_energy(m0, |velocity|)`` (J)."""
    return total_energy(rest_mass, speed(velocity))
