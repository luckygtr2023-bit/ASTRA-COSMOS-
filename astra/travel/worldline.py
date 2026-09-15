"""Worldline construction. Reconciled.

Linear interpolation scaffold is deterministic and documented as placeholder
for strong-field regimes. For flat/Minkowski travel it is exact (inertial
worldlines are straight). For curved metrics the engine may optionally
replace with geodesic integration via astra.spacetime.geodesics.
"""
from __future__ import annotations

import math
from typing import List

from .config import TravelConfig
from .errors import TravelNumericalError, TravelUnsupportedError
from .types import Provenance, Vec3, Worldline, WorldlineSample


def _finite(x: float) -> float:
    if math.isnan(x) or math.isinf(x):
        raise TravelNumericalError("non-finite value in worldline construction")
    return x


def _lerp(a: Vec3, b: Vec3, t: float) -> Vec3:
    return a * (1.0 - t) + b * t


def build_worldline(
    departure_pos: Vec3,
    departure_time: float,
    arrival_pos: Vec3,
    arrival_time: float,
    proper_time_total: float,
    config: TravelConfig,
    *,
    n_samples: int | None = None,
    observer_frame: str = "world",
    provenance: Provenance = Provenance.SIMULATED_DATA,
) -> Worldline:
    """Deterministic piecewise-linear worldline.

    For inertial flat travel this is exact. For curved metrics it is a
    scaffold — the engine may substitute a geodesic solution where a metric
    provider is available.
    """
    if not isinstance(departure_pos, Vec3):
        from .types import _to_vec3

        departure_pos = _to_vec3(departure_pos)
    if not isinstance(arrival_pos, Vec3):
        from .types import _to_vec3

        arrival_pos = _to_vec3(arrival_pos)

    departure_time = _finite(departure_time)
    arrival_time = _finite(arrival_time)
    proper_time_total = _finite(proper_time_total)

    if arrival_time < departure_time:
        raise TravelUnsupportedError("backward coordinate-time worldlines are not supported")
    if proper_time_total < 0:
        raise TravelNumericalError("proper_time_total must be >=0")
    if arrival_time == departure_time and (arrival_pos - departure_pos).norm() > 1e-12:
        # instantaneous spatial displacement without time is spacelike → not allowed for matter
        raise TravelNumericalError("instantaneous spatial displacement requires non-zero coordinate duration")

    if n_samples is None:
        n_samples = max(config.worldline_min_samples, min(config.worldline_max_samples, 64))
    if n_samples < 2:
        raise TravelNumericalError("n_samples must be >= 2")
    if n_samples > config.worldline_max_samples:
        n_samples = config.worldline_max_samples

    dt_total = arrival_time - departure_time
    samples: List[WorldlineSample] = []
    for i in range(n_samples):
        t = i / (n_samples - 1) if n_samples > 1 else 0.0
        samples.append(
            WorldlineSample(
                coordinate_time_s=_finite(departure_time + dt_total * t),
                proper_time_s=_finite(proper_time_total * t),
                position=_lerp(departure_pos, arrival_pos, t),
                observer_frame=observer_frame,
            )
        )
    return Worldline(samples=tuple(samples), provenance=provenance)


def build_geodesic_worldline(
    metric,
    initial_coords,
    initial_four_velocity,
    proper_time_limit_s: float,
    steps: int = 400,
    provenance: Provenance = Provenance.SIMULATED_DATA,
):
    """Build worldline via authoritative geodesic integration (curved metric).

    Delegates to astra.spacetime.geodesics.integrate_geodesic. Converts
    the resulting GeodesicSolution into a travel Worldline for provenance
    and observer representation.
    """
    from astra.spacetime.geodesics import integrate_geodesic as _integrate

    sol = _integrate(metric, initial_coords, initial_four_velocity, float(proper_time_limit_s), steps=steps)
    # sol.parameters are proper times, sol.events are SpacetimeEvents (or raw tuples depending on version)
    # Adapt to travel WorldlineSample
    samples = []
    for param, event in zip(sol.parameters, sol.events):
        # event may be SpacetimeEvent or tuple
        if hasattr(event, "x"):
            pos = Vec3(event.x, event.y, event.z)
            ct = event.ct_m
            from astra.relativity.core import SPEED_OF_LIGHT

            coord_time = ct / SPEED_OF_LIGHT
        else:
            # tuple (ct, x, y, z)
            ct, x, y, z = event
            from astra.relativity.core import SPEED_OF_LIGHT

            coord_time = ct / SPEED_OF_LIGHT
            pos = Vec3(x, y, z)
        samples.append(
            WorldlineSample(
                coordinate_time_s=float(coord_time),
                proper_time_s=float(param),
                position=pos,
                observer_frame="world",
            )
        )
    return Worldline(samples=tuple(samples), provenance=provenance)
