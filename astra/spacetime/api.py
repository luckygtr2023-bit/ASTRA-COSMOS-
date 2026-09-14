"""ASTRA Spacetime - authoritative facade API.

Contract: upstream systems (Spacecraft, Orbital, future engines) query THIS
module only. Dependency direction (no reverse edges, no cycles):

    CORE -> MATHEMATICS -> PHYSICS -> RELATIVITY -> BLACK-HOLE -> SPACETIME

Conversions: cartesian events + 3-velocities are converted into the
metric's chart (with the full velocity Jacobian) so callers can stay in
SI cartesian space while integration runs in (ct, r, theta, phi).

Deterministic pure functions over immutable inputs.
"""

from __future__ import annotations

import math
from typing import Dict, Sequence, Tuple

from astra.mathematics import Vector3
from astra.relativity.core import SPEED_OF_LIGHT
from astra.relativity.exceptions import LightSpeedViolation
from astra.relativity.four_vectors import SpacetimeIntervalType
from astra.spacetime import causality, connection, curvature, geodesics
from astra.spacetime.events import (
    CHART_CARTESIAN,
    CHART_SPHERICAL,
    SpacetimeEvent,
    Worldline,
    cartesian_to_spherical,
    spherical_to_cartesian,
)
from astra.spacetime.exceptions import InvalidCoordinateError
from astra.spacetime.metric import (
    KerrMetric,
    MetricField,
    MinkowskiMetric,
    NumericalMetric,
    SchwarzschildMetric,
    SpacetimeModel,
    Tensor4,
)


def create_event(t_sec: float, x: float, y: float, z: float,
                 chart: str = CHART_CARTESIAN) -> SpacetimeEvent:
    """Create a validated, immutable SpacetimeEvent (SI in, ct stored)."""
    return SpacetimeEvent.from_coordinates(t_sec, x, y, z, chart)


def minkowski_metric() -> MinkowskiMetric:
    return MinkowskiMetric()


def schwarzschild_metric(mass_kg: float) -> SchwarzschildMetric:
    """SchwarzschildMetric built from the black-hole layer's exact r_s."""
    return SchwarzschildMetric(mass_kg)


def kerr_metric(mass_kg: float, spin_param: float) -> KerrMetric:
    return KerrMetric(mass_kg, spin_param)


def numerical_metric(field_callable, chart: str = CHART_CARTESIAN) -> NumericalMetric:
    return NumericalMetric(field_callable, chart)


def get_metric_tensor(
    model: SpacetimeModel,
    coordinates: Sequence[float],
    mass_kg: float = 1.989e30,
    spin_param: float = 0.0,
) -> Tensor4:
    """Metric tensor g_mu_nu for a model at given chart coordinates.

    Convenience dispatcher over the metric classes; pass mass/spin as
    needed. Prefer constructing a MetricField once and reusing it.
    """
    metric = _metric_for(model, mass_kg, spin_param)
    return metric.tensor(coordinates)


def _metric_for(model: SpacetimeModel, mass_kg: float, spin_param: float) -> MetricField:
    if model is SpacetimeModel.MINKOWSKI:
        return MinkowskiMetric()
    if model is SpacetimeModel.SCHWARZSCHILD:
        return SchwarzschildMetric(mass_kg)
    if model is SpacetimeModel.KERR:
        return KerrMetric(mass_kg, spin_param)
    raise InvalidCoordinateError(f"get_metric_tensor cannot dispatch {model!r}; "
                                 "construct a NumericalMetric explicitly")


def calculate_christoffel(metric: MetricField, coordinates: Sequence[float]):
    """Gamma^rho_{mu nu} at chart coordinates (4x4x4 nested tuples)."""
    return connection.christoffel_symbols(metric, coordinates)


def calculate_riemann(metric: MetricField, coordinates: Sequence[float]):
    """R^rho_{sigma mu nu} at chart coordinates."""
    return curvature.riemann_tensor(metric, coordinates)


def calculate_ricci_scalar(metric: MetricField, coordinates: Sequence[float]) -> float:
    """Ricci scalar R at chart coordinates."""
    return curvature.ricci_scalar(metric, coordinates)


def calculate_tidal_acceleration(
    metric: MetricField,
    coordinates: Sequence[float],
    four_velocity: Sequence[float],
    separation_vector: Sequence[float],
) -> Tuple[float, float, float, float]:
    """Geodesic-deviation acceleration A^mu = -R^mu_{nu rho sigma} U^nu X^rho U^sigma."""
    return curvature.tidal_acceleration(metric, coordinates, four_velocity, separation_vector)


def classify_separation(
    metric: MetricField, event_a: SpacetimeEvent, event_b: SpacetimeEvent,
    tolerance: float = 1.0e-9,
) -> SpacetimeIntervalType:
    """Causal classification of a separation via the active metric."""
    return causality.classify_interval(metric, event_a.coordinates(), event_b.coordinates(),
                                       tolerance)


def event_to_chart(metric: MetricField, event: SpacetimeEvent) -> Tuple[float, float, float, float]:
    """Chart coordinates (ct, ...) for a cartesian event under the metric's chart."""
    if metric.chart == CHART_CARTESIAN:
        return event.coordinates()
    r, theta, phi = cartesian_to_spherical(event.x, event.y, event.z)
    return (event.ct_m, r, theta, phi)


def cartesian_state_to_chart(
    metric: MetricField,
    event: SpacetimeEvent,
    velocity3,
    massless: bool = False,
) -> Tuple[Tuple[float, float, float, float], Tuple[float, float, float, float]]:
    """Convert a cartesian event + 3-velocity into chart coordinates.

    Metric-correct construction (no flat-SR shortcut):
      1. The coordinate velocity w^i = dx^i/dt is transformed with the
         analytic Jacobian of the cartesian->chart position map (t is the
         same coordinate in both charts, so dt-component ratios transform
         like positions).
      2. For MASSIVE particles the temporal component follows from the
         normalization g_mu_nu u^mu u^nu = -c^2 with u^mu = u^0 (1, w^i):
             u^0 = c / sqrt( -[ g_00 + 2 g_0i w^i + g_ij w^i w^j ] )
         which reproduces gamma*c in flat spacetime and includes the
         gravitational contribution in curved charts. A bracket >= 0 means
         the 3-velocity reaches/exceeds LOCAL light speed and raises the
         relativity layer's LightSpeedViolation.
      3. For MASSLESS rays, an affine parameterization d(lambda) = dct is
         used: u = (1, w^i); the null condition then holds automatically
         for physical input speeds.
    """
    C = SPEED_OF_LIGHT
    if not isinstance(velocity3, Vector3):
        raise InvalidCoordinateError("velocity3 must be an astra.mathematics.Vector3")
    v_mag = velocity3.magnitude()
    if v_mag == 0.0 and massless:
        raise InvalidCoordinateError("Null geodesic needs a nonzero velocity")
    x0 = event.ct_m

    if metric.chart == CHART_CARTESIAN:
        if massless:
            s = 1.0 / v_mag  # u^0 = 1 normalization: dlambda = dct (lambda in m)
            u = (1.0, velocity3.x * s / 1.0, velocity3.y * s, velocity3.z * s)
            # u^i = dx^i/dlambda = v^i/|v|; null: -1 + sum = 0 exactly.
            return (x0, event.x, event.y, event.z), u
        w = (C, velocity3.x, velocity3.y, velocity3.z)  # dx^mu/dt, m/s slots
        g = metric.tensor((x0, event.x, event.y, event.z))
        ww = sum(g[a][b] * w[a] * w[b] for a in range(4) for b in range(4))
        if ww >= 0.0:
            raise LightSpeedViolation(
                f"3-velocity |v| = {v_mag!r} m/s reaches/exceeds local light speed."
            )
        dt_dtau = C / math.sqrt(-ww)  # dimensionless dt/dtau
        u0 = C * dt_dtau              # dct/dtau (m/s)
        return (x0, event.x, event.y, event.z), (
            u0, dt_dtau * velocity3.x, dt_dtau * velocity3.y, dt_dtau * velocity3.z,
        )

    # Spherical/BL chart: position conversion + coordinate-velocity Jacobian.
    r, theta, phi = cartesian_to_spherical(event.x, event.y, event.z)
    x, y, z = event.x, event.y, event.z
    vx, vy, vz = velocity3.x, velocity3.y, velocity3.z
    rho = math.hypot(x, y)
    w_r = (x * vx + y * vy + z * vz) / r
    w_th = ((x * vx + y * vy) * z / rho - z * vz * rho) / (r * r)
    w_ph = (x * vy - y * vx) / (rho * rho)

    g = metric.tensor((x0, r, theta, phi))
    if massless:
        # dlambda = dct: u^mu = dx^mu/d(ct); spatial slots carry w^i / c (1/m).
        return (x0, r, theta, phi), (1.0, w_r / C, w_th / C, w_ph / C)
    w = (C, w_r, w_th, w_ph)  # dx^mu/dt; g(w, w) has units m^2/s^2
    ww = sum(g[a][b] * w[a] * w[b] for a in range(4) for b in range(4))
    if ww >= 0.0:
        raise LightSpeedViolation(
            f"3-velocity |v| = {v_mag!r} m/s reaches/exceeds local light speed."
        )
    dt_dtau = C / math.sqrt(-ww)
    return (x0, r, theta, phi), (C * dt_dtau, dt_dtau * w_r, dt_dtau * w_th, dt_dtau * w_ph)


def integrate_geodesic(
    metric: MetricField,
    initial_event: SpacetimeEvent,
    initial_velocity,
    parameter_limit: float,
    steps: int = 400,
    massless: bool = False,
    adaptive: bool = False,
) -> geodesics.GeodesicSolution:
    """Facade geodesic integration from a cartesian event + 3-velocity.

    Converts the initial state into the metric's chart (see
    cartesian_state_to_chart), integrates with the deterministic ASTRA ODE
    steppers, and applies horizon guards (HorizonCrossingError on approach).
    """
    coords0, u0 = cartesian_state_to_chart(metric, initial_event, initial_velocity, massless)
    return geodesics.integrate_geodesic(
        metric, coords0, u0, parameter_limit,
        steps=steps, adaptive=adaptive,
    )


def integrate_geodesic_chart(
    metric: MetricField,
    initial_coords: Sequence[float],
    initial_four_velocity: Sequence[float],
    parameter_limit: float,
    steps: int = 400,
    adaptive: bool = False,
) -> geodesics.GeodesicSolution:
    """Chart-native geodesic integration (no conversions)."""
    return geodesics.integrate_geodesic(
        metric, initial_coords, initial_four_velocity, parameter_limit,
        steps=steps, adaptive=adaptive,
    )
