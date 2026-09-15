"""Two-body analytical propagation.

For elliptic and hyperbolic orbits, propagate by advancing the mean
anomaly by n * dt, solving the Kepler equation, and converting back to
state vectors. For parabolic orbits, propagate using Barker's equation.

The propagation is a pure function of (state, dt) — no wall-clock, no
RNG, no hidden state.
"""
from __future__ import annotations
import math

from astra.orbital.state import OrbitalState
from astra.orbital.elements import (
    state_to_elements, elements_to_state, ClassicalOrbitalElements,
)
from astra.orbital.anomalies import (
    eccentric_to_true, true_to_mean_elliptic, mean_to_true_elliptic,
    hyperbolic_to_true, true_to_mean_hyperbolic, mean_to_true_hyperbolic,
    true_to_mean_parabolic, mean_to_true_parabolic,
)
from astra.orbital.constants import PARABOLIC_TOL


def _propagate_elements(el: ClassicalOrbitalElements,
                        dt: float) -> ClassicalOrbitalElements:
    e = el.eccentricity
    mu = el.mu
    if el.is_parabolic:
        # Parabolic propagation via Barker.
        M0 = true_to_mean_parabolic(el.true_anomaly)
        # Barker time scale: t = (1/2) sqrt(p^3/mu) * (D + D^3/3)
        # Hence M(t) = M0 + (2 * sqrt(mu / p^3)) * dt
        n_par = 2.0 * math.sqrt(mu / (el.semi_latus_rectum ** 3))
        M = M0 + n_par * dt
        nu_new = mean_to_true_parabolic(M)
        return ClassicalOrbitalElements(
            semi_latus_rectum=el.semi_latus_rectum,
            eccentricity=1.0,
            inclination=el.inclination,
            raan=el.raan,
            argument_of_periapsis=el.argument_of_periapsis,
            true_anomaly=nu_new,
            mu=mu,
            is_circular=False,
            is_equatorial=el.is_equatorial,
            is_parabolic=True,
        )
    a = el.semi_major_axis
    if e < 1.0:
        # Elliptic
        n = math.sqrt(mu / (a ** 3))
        M0 = true_to_mean_elliptic(el.true_anomaly, e)
        M = M0 + n * dt
        nu_new = mean_to_true_elliptic(M % (2.0 * math.pi), e)
        return ClassicalOrbitalElements(
            semi_latus_rectum=el.semi_latus_rectum,
            eccentricity=e,
            inclination=el.inclination,
            raan=el.raan,
            argument_of_periapsis=el.argument_of_periapsis,
            true_anomaly=nu_new,
            mu=mu,
            is_circular=el.is_circular,
            is_equatorial=el.is_equatorial,
            is_parabolic=False,
        )
    # Hyperbolic
    n = math.sqrt(mu / (-a) ** 3)
    M0 = true_to_mean_hyperbolic(el.true_anomaly, e)
    M = M0 + n * dt
    nu_new = mean_to_true_hyperbolic(M, e)
    return ClassicalOrbitalElements(
        semi_latus_rectum=el.semi_latus_rectum,
        eccentricity=e,
        inclination=el.inclination,
        raan=el.raan,
        argument_of_periapsis=el.argument_of_periapsis,
        true_anomaly=nu_new,
        mu=mu,
        is_circular=False,
        is_equatorial=el.is_equatorial,
        is_parabolic=False,
    )


def propagate(state: OrbitalState, dt: float) -> OrbitalState:
    """Propagate a two-body state forward by dt (simulation seconds).

    dt may be negative (backward propagation). Zero dt returns a copy.
    """
    if dt == 0.0:
        return OrbitalState(position=state.position,
                            velocity=state.velocity,
                            mu=state.mu,
                            epoch=state.epoch)
    el = state_to_elements(state)
    el2 = _propagate_elements(el, dt)
    return elements_to_state(el2, epoch=state.epoch + dt)


def propagate_state(state: OrbitalState, dt: float) -> OrbitalState:
    """Alias for propagate(); provided for symmetry with future APIs."""
    return propagate(state, dt)
