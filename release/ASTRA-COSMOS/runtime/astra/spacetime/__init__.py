"""ASTRA Spacetime layer.

Dependency direction:
    CORE -> MATHEMATICS -> PHYSICS -> RELATIVITY -> BLACK-HOLE -> SPACETIME

General geometric infrastructure for fixed-background metrics under the
test-particle approximation (no Einstein Field Equation solving):

    - MetricField protocol: Minkowski (cartesian), Schwarzschild
      (spherical, ANALYTIC derivatives), Kerr (Boyer-Lindquist, numeric
      derivatives), arbitrary NumericalMetric (4th-order central
      differences).
    - Christoffel symbols, Riemann / Ricci / Einstein tensors, Kretschmann
      scalar, geodesic-deviation (tidal) operator.
    - Causal classification via the ACTIVE metric (linearized local
      interval; exact for Minkowski).
    - Deterministic geodesic integration on astra.mathematics.ode steppers
      with per-stage horizon and NaN guards (HorizonCrossingError /
      GeodesicDivergenceError).

Tensor conventions (all modules): x^mu = (ct, spatial), signature
(-,+,+,+), Levi-Civita connection (zero torsion), Riemann sign per
curvature.py docstring ("positive curvature focuses geodesics").

Out of scope (deferred): Kruskal-Szekeres regular coordinates, metric
backreaction / numerical relativity, non-diagonal light-cone tracing.

Authority: stateless calculation layer over immutable value objects.
Persistence: plain-primitive to_dict / from_dict on events and worldlines;
tensors are derived state and are never serialized.

Determinism: 100% deterministic - no RNG, no wall-clock, no global state.
"""
from astra.spacetime.exceptions import (
    SpacetimeError,
    InvalidCoordinateError,
    DegenerateMetricError,
    HorizonCrossingError,
    GeodesicDivergenceError,
)
from astra.spacetime.events import (
    CHART_CARTESIAN,
    CHART_SPHERICAL,
    SpacetimeEvent,
    Worldline,
    cartesian_to_spherical,
    spherical_to_cartesian,
)
from astra.spacetime.metric import (
    SpacetimeModel,
    MetricField,
    MinkowskiMetric,
    SchwarzschildMetric,
    KerrMetric,
    NumericalMetric,
    DIFF_STEP,
    DET_REL_TOL,
)
from astra.spacetime.connection import christoffel_symbols, christoffel_derivative
from astra.spacetime.curvature import (
    riemann_tensor,
    ricci_tensor,
    ricci_scalar,
    einstein_tensor,
    kretschmann_scalar,
    tidal_acceleration,
)
from astra.spacetime.geodesics import (
    GeodesicSolution,
    geodesic_rhs,
    integrate_geodesic as integrate_geodesic_chart,
)
from astra.spacetime import api
from astra.spacetime.api import (
    create_event,
    minkowski_metric,
    schwarzschild_metric,
    kerr_metric,
    numerical_metric,
    get_metric_tensor,
    calculate_christoffel,
    calculate_riemann,
    calculate_ricci_scalar,
    calculate_tidal_acceleration,
    classify_separation,
    event_to_chart,
    cartesian_state_to_chart,
    integrate_geodesic,
)

__all__ = [
    # exceptions
    "SpacetimeError", "InvalidCoordinateError", "DegenerateMetricError",
    "HorizonCrossingError", "GeodesicDivergenceError",
    # events
    "CHART_CARTESIAN", "CHART_SPHERICAL", "SpacetimeEvent", "Worldline",
    "cartesian_to_spherical", "spherical_to_cartesian",
    # metrics
    "SpacetimeModel", "MetricField", "MinkowskiMetric", "SchwarzschildMetric",
    "KerrMetric", "NumericalMetric", "DIFF_STEP", "DET_REL_TOL",
    # connection & curvature
    "christoffel_symbols", "christoffel_derivative",
    "riemann_tensor", "ricci_tensor", "ricci_scalar", "einstein_tensor",
    "kretschmann_scalar", "tidal_acceleration",
    # geodesics
    "GeodesicSolution", "geodesic_rhs", "integrate_geodesic_chart",
    # facade
    "api", "create_event", "minkowski_metric", "schwarzschild_metric",
    "kerr_metric", "numerical_metric", "get_metric_tensor",
    "calculate_christoffel", "calculate_riemann", "calculate_ricci_scalar",
    "calculate_tidal_acceleration", "classify_separation", "event_to_chart",
    "cartesian_state_to_chart", "integrate_geodesic",
]
