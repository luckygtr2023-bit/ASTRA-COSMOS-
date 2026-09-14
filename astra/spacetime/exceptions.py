"""ASTRA Spacetime - exceptions.

Contract: every Spacetime-layer error derives from
``astra.core.exceptions.AstraError``. Validation errors additionally derive
from ``ValueError``.

NOTE (Agent LM): the handoff referenced ``PermissionClient.mutate()`` and a
``Serializable`` base class; neither exists in this repository. Authority in
ASTRA is enforced by ``astra.core.threading``; this layer is a pure
calculation layer (immutable value objects, no mutable simulation state) and
persistence uses ``to_dict`` / ``from_dict`` plain primitives.
"""

from astra.core.exceptions import AstraError


class SpacetimeError(AstraError):
    """Base Spacetime-layer error."""


class InvalidCoordinateError(SpacetimeError, ValueError):
    """Raised when a coordinate tuple is malformed, non-finite or NaN."""


class DegenerateMetricError(SpacetimeError):
    """Raised when a metric tensor is singular (or effectively singular).

    Cases: |det g| at/below tolerance, evaluation on a coordinate axis
    (theta = 0), or outside the coordinate patch (r at/inside the horizon
    for Boyer-Lindquist/Schwarzschild charts).
    """


class HorizonCrossingError(SpacetimeError):
    """Raised when a geodesic integration step reaches or crosses a horizon.

    Standard (t, r, theta, phi) coordinates are singular at horizons; the
    integrator halts BEFORE the crossing to prevent NaN/Inf corruption of
    downstream Spacecraft/Orbital systems. Kruskal-Szekeres regular
    coordinates are deferred to a future phase.
    """


class GeodesicDivergenceError(SpacetimeError):
    """Raised when a geodesic integration produces non-finite state.

    Defensive stop: any NaN/Inf appearing mid-integration (e.g. from
    pathological inputs) halts the run immediately.
    """
