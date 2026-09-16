"""ASTRA Spacetime - geodesic integration.

Contract: d^2 x^mu / d lambda^2 = -Gamma^mu_{alpha beta} (dx^alpha/d lambda)
(dx^beta/d lambda), integrated with the ASTRA mathematics-layer ODE steppers
(rk4_step / rk45_step from astra.mathematics.ode - no reimplementation).

Parameterization: proper time tau (seconds) for timelive worldlines
(normalization u.mu u^mu = -c^2) or an affine parameter lambda (1/m) for
null worldlines (g u u = 0).

Robustness (per handoff sections 3, 23-P2, 26-2):
    - HORIZON GUARD: every proposed step AND every internal RK stage point
      is checked against the metric's horizon guard; a trajectory reaching
      or crossing the horizon raises HorizonCrossingError (mid-step
      leap-frogging is impossible because stage points are validated too).
    - NaN/Inf at any stage raises GeodesicDivergenceError.
    - Fully deterministic: fixed initial step, fixed stepper, no RNG.

Coordinate charts: the integration runs in the metric's own chart
(cartesian for Minkowski, spherical/BL for Schwarzschild/Kerr). Facade
helpers in api.py convert cartesian events + 3-velocities into chart data.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, List, Sequence, Tuple

from astra.mathematics.ode import rk4_step, rk45_step
from astra.spacetime.connection import christoffel_symbols
from astra.spacetime.events import CHART_SPHERICAL, SpacetimeEvent, Worldline
from astra.spacetime.exceptions import (
    GeodesicDivergenceError,
    HorizonCrossingError,
    InvalidCoordinateError,
)
from astra.spacetime.metric import MetricField, _validate_coords

State = Tuple[float, float, float, float, float, float, float, float]  # (x^mu, u^mu)


@dataclass(frozen=True)
class GeodesicSolution:
    """Immutable geodesic integration result.

    parameters: increasing lambda or tau values (incl. the initial 0).
    coordinates: chart-coordinate 4-tuples x^mu(lambda).
    four_velocities: chart-coordinate tangent components u^mu(lambda).
    """

    parameters: Tuple[float, ...]
    coordinates: Tuple[State, ...]
    four_velocities: Tuple[Tuple[float, float, float, float], ...]
    terminated: str  # "completed" | "horizon"

    @property
    def final_coordinates(self) -> Tuple[float, float, float, float]:
        return self.coordinates[-1]

    def to_worldline(self, chart: str) -> Worldline:
        """Chart coordinates converted to cartesian SpacetimeEvents.

        For spherical charts, events carry (r, theta, phi) in the spatial
        slots with chart = CHART_SPHERICAL (no cartesian conversion is
        applied, so nothing is lost for downstream relativity checks).
        """
        samples = tuple(
            (p, SpacetimeEvent(x[0], x[1], x[2], x[3], chart))
            for p, x in zip(self.parameters, self.coordinates)
        )
        return Worldline(samples)


def geodesic_rhs(metric: MetricField) -> Callable[[float, State], State]:
    """Build the deterministic geodesic right-hand side for a metric."""
    cache: dict = {}

    def rhs(_lambda: float, y: State) -> State:
        x = y[:4]
        u = y[4:]
        key = x
        gamma = cache.get(key)
        if gamma is None:
            gamma = christoffel_symbols(metric, x)
            if len(cache) > 4096:
                cache.clear()
            cache[key] = gamma
        acc = [0.0] * 4
        for mu in range(4):
            s = 0.0
            for alpha in range(4):
                ua = u[alpha]
                if ua == 0.0:
                    continue
                for beta in range(4):
                    ub = u[beta]
                    if ub == 0.0:
                        continue
                    s += gamma[mu][alpha][beta] * ua * ub
            acc[mu] = -s
        return tuple(u) + tuple(acc)

    return rhs


def _horizon_limit(metric: MetricField) -> float:
    """Radial horizon guard for spherical charts (0.0 for cartesian)."""
    if metric.chart != CHART_SPHERICAL:
        return 0.0
    if metric.model.value == "SCHWARZSCHILD":
        return metric.rs_m
    if metric.model.value == "KERR":
        return metric.r_plus_m
    return 0.0


def _check_state(metric: MetricField, y: State, horizon: float) -> None:
    for v in y:
        if math.isnan(v) or math.isinf(v):
            raise GeodesicDivergenceError(
                "Geodesic integration produced non-finite state; halting."
            )
    if horizon > 0.0 and y[1] <= horizon * (1.0 + 1.0e-12):
        raise HorizonCrossingError(
            f"Geodesic reached r = {y[1]!r} m, at/inside the horizon "
            f"{horizon!r} m; integration halted before coordinate breakdown."
        )


def integrate_geodesic(
    metric: MetricField,
    initial_coords: Sequence[float],
    initial_four_velocity: Sequence[float],
    parameter_limit: float,
    steps: int = 400,
    adaptive: bool = False,
    rtol: float = 1.0e-10,
) -> GeodesicSolution:
    """Integrate a geodesic in the metric's chart. Deterministic.

    Args:
        metric: the fixed background.
        initial_coords: x^mu(0) in the metric's chart (validated + patch-guarded).
        initial_four_velocity: u^mu = dx^mu/d(param) in chart coordinates.
        parameter_limit: total proper time (s, timelike) or affine span (null).
        steps: number of uniform output steps (adaptive refines internally).
        adaptive: use the DOPRI5(4) embedded stepper (rk45_step) with the
            same deterministic input; otherwise classic RK4 fixed step.

    Returns:
        GeodesicSolution (immutable). ``terminated == "horizon"`` marks a
        run halted exactly at the guard band.
    """
    if isinstance(parameter_limit, bool) or not isinstance(parameter_limit, (int, float)) \
            or math.isnan(parameter_limit) or math.isinf(parameter_limit) or parameter_limit <= 0.0:
        raise InvalidCoordinateError(
            f"parameter_limit must be a positive finite number, got {parameter_limit!r}"
        )
    if isinstance(steps, bool) or not isinstance(steps, int) or steps < 1 or steps > 200_000:
        raise InvalidCoordinateError(f"steps must be an int in [1, 200000], got {steps!r}")

    x0 = _validate_coords(initial_coords, metric.chart)
    u0 = tuple(
        float(v) for v in initial_four_velocity
    )
    if len(u0) != 4:
        raise InvalidCoordinateError("initial_four_velocity must be a 4-tuple")
    for v in u0:
        if math.isnan(v) or math.isinf(v):
            raise InvalidCoordinateError("initial_four_velocity contains non-finite components")

    rhs = geodesic_rhs(metric)
    horizon = _horizon_limit(metric)

    state: State = tuple(x0) + tuple(u0)
    _check_state(metric, state, horizon)

    h0 = parameter_limit / steps
    params: List[float] = [0.0]
    coords_out: List[State] = [tuple(x0)]
    vels_out: List[Tuple[float, float, float, float]] = [tuple(u0)]
    terminated = "completed"

    lam = 0.0
    h_current = h0
    accepted = 0
    max_inner = 2_000_000
    while lam < parameter_limit - 1e-15 * parameter_limit:
        if accepted >= max_inner:
            raise GeodesicDivergenceError("Exceeded maximum inner integration steps")
        step = min(h_current, parameter_limit - lam)
        remaining = parameter_limit - lam
        if adaptive:
            # Subdivide the (possibly grown) step so guard checks happen
            # at stage granularity; rk45_step validates its own stages.
            y5, _y4, err = rk45_step(rhs, lam, state, step)
            scale = max(1.0e-30, max(abs(v) for v in y5))
            e = err / (rtol * scale + 1e-30)
            if e <= 1.0:
                # Validate the PROPOSED endpoint before accepting (mid-step
                # horizon crossing cannot slip through; see module docstring).
                _check_state(metric, y5, horizon)
                state = y5
                lam += step
                accepted += 1
                if e > 0:
                    h_current = step * min(5.0, max(0.2, 0.9 * e ** (-0.2)))
            else:
                h_current = step * max(0.1, 0.9 * e ** (-0.25))
                if h_current < 1e-15 * max(1.0, abs(parameter_limit)):
                    raise GeodesicDivergenceError("Adaptive step size underflow")
                continue
        else:
            # Validate each RK stage point to catch intra-step crossings.
            k1 = rhs(lam, state)
            mid1 = tuple(s + 0.5 * step * k for s, k in zip(state, k1))
            _check_state(metric, mid1, horizon)
            k2 = rhs(lam + 0.5 * step, mid1)
            mid2 = tuple(s + 0.5 * step * k for s, k in zip(state, k2))
            _check_state(metric, mid2, horizon)
            k3 = rhs(lam + 0.5 * step, mid2)
            mid3 = tuple(s + step * k for s, k in zip(state, k3))
            _check_state(metric, mid3, horizon)
            k4 = rhs(lam + step, mid3)
            state = tuple(
                s + step / 6.0 * (a + 2.0 * b + 2.0 * c + d)
                for s, a, b, c, d in zip(state, k1, k2, k3, k4)
            )
            _check_state(metric, state, horizon)
            lam += step
            accepted += 1
        params.append(lam)
        coords_out.append(tuple(state[:4]))
        vels_out.append(tuple(state[4:]))

    return GeodesicSolution(
        parameters=tuple(params),
        coordinates=tuple(coords_out),
        four_velocities=tuple(vels_out),
        terminated=terminated,
    )
