"""Proper-time and time-dilation tests (physics anchors)."""
import math

import pytest

from astra.mathematics import Vector3
from astra.relativity.core import SPEED_OF_LIGHT as C
from astra.relativity.exceptions import SpacelikeIntervalError
from astra.relativity.gr_foundations import schwarzschild_radius
from astra.spacetime import (
    MinkowskiMetric,
    SchwarzschildMetric,
    SpacetimeEvent,
    Worldline,
)
from astra.spacetime.events import CHART_CARTESIAN
from astra.temporal import (
    InvalidWorldlineError,
    flat_proper_time,
    gravitational_time_dilation,
    metric_proper_time,
    velocity_time_dilation,
)

MASS_SUN = 1.989e30


def _wl(*t_xyz):
    """Worldline from (t, x, y, z) tuples with t in seconds."""
    samples = []
    for t, x, y, z in t_xyz:
        samples.append((t, SpacetimeEvent.from_coordinates(t, x, y, z, CHART_CARTESIAN)))
    return Worldline(tuple(samples))


class TestFlatProperTime:
    def test_anchor_low_velocity_tau_approaches_t(self):
        # v = 10 m/s: tau must equal t to double precision (relativity
        # convention: tau = t/gamma, gamma ~ 1).
        wl = _wl((0.0, 0.0, 0.0, 0.0), (1.0, 10.0, 0.0, 0.0))
        tau = flat_proper_time(wl)
        # gamma's Taylor branch truncates at O(beta^4): relative tau error
        # is bounded by beta^2/2 ~ 5.6e-16 at 10 m/s - the honest limit.
        assert math.isclose(tau, 1.0, rel_tol=1e-15)

    def test_anchor_inertial_matches_relativity_convention(self):
        # gamma at 0.6c = 1.25 exactly: tau = t / gamma.
        wl = _wl((0.0, 0.0, 0.0, 0.0), (2.0, 0.6 * C * 2.0, 0.0, 0.0))
        assert flat_proper_time(wl) == pytest.approx(2.0 / 1.25, rel=1e-14)

    def test_anchor_null_worldline_tau_zero(self):
        # Light ray: |dx| = c dt -> tau = 0 exactly.
        wl = _wl((0.0, 0.0, 0.0, 0.0), (2.0, 2.0 * C, 0.0, 0.0))
        assert flat_proper_time(wl) == 0.0

    def test_anchor_null_with_transverse(self):
        wl = _wl((0.0, 0.0, 0.0, 0.0), (1.0, 0.6 * C, 0.8 * C, 0.0))
        # 3-4-5 null ray: cancellation of c^2(1 - 0.36 - 0.64) leaves FP
        # residue; honest tau bound ~ |residue|/2c ~ 1e-8 s.
        assert flat_proper_time(wl) == pytest.approx(0.0, abs=1e-7)

    def test_spacelike_segment_rejected(self):
        wl = _wl((0.0, 0.0, 0.0, 0.0), (1.0, 2.0 * C, 0.0, 0.0))
        with pytest.raises(SpacelikeIntervalError):
            flat_proper_time(wl)

    def test_mixed_segments(self):
        # 1 s at rest, then 1 s on a null ray: tau = 1 + 0.
        wl = _wl((0.0, 0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0),
                 (2.0, C, 0.0, 0.0))
        assert flat_proper_time(wl) == pytest.approx(1.0, rel=1e-12)

    def test_single_sample_rejected(self):
        with pytest.raises(InvalidWorldlineError):
            flat_proper_time(_wl((0.0, 0.0, 0.0, 0.0)))

    def test_non_worldline_rejected(self):
        with pytest.raises(InvalidWorldlineError):
            flat_proper_time([(0.0, None)])


class TestMetricProperTime:
    def test_flat_geodesic_tau_is_parameter(self):
        # u = (c, 0,0,0): proper time == parameter span.
        sol = metric_proper_time(MinkowskiMetric(), (0.0, 0.0, 0.0, 0.0),
                                 (C, 0.0, 0.0, 0.0), 1.0, steps=50)
        assert sol.parameters[-1] == pytest.approx(1.0, rel=1e-12)

    def test_schwarzschild_circular_orbit_rate(self):
        # dtau/dt = sqrt(1 - 3 r_g / r) for a circular orbit (r = 10 r_g).
        # Half an orbit keeps the fixed-step integration well resolved
        # (1 coordinate second would be ~1200 orbits at this radius).
        sm = SchwarzschildMetric(MASS_SUN)
        rg = 0.5 * sm.rs_m
        r0 = 10.0 * rg
        omega = C * math.sqrt(rg / r0 ** 3)   # Kepler: omega = c sqrt(rg/r^3)
        gamma = 1.0 / math.sqrt(1.0 - 3.0 * rg / r0)
        coord_span = 0.5 * (2.0 * math.pi / omega)   # half orbit, seconds
        # dt/dtau = gamma  =>  tau limit for a coordinate span S is S/gamma.
        sol = metric_proper_time(
            sm, (0.0, r0, math.pi / 2, 0.0),
            (gamma * C, 0.0, 0.0, gamma * omega),
            coord_span / gamma, steps=2000,
        )
        # Coordinate time elapsed matches the half-orbit span:
        assert sol.final_coordinates[0] / C == pytest.approx(coord_span, rel=1e-6)
        # Proper time accumulated follows the circular-orbit rate:
        expected_tau = coord_span * math.sqrt(1.0 - 3.0 * rg / r0)
        assert sol.parameters[-1] == pytest.approx(expected_tau, rel=1e-4)
        # Orbit stayed circular (r unchanged to 1e-6 relative):
        radii = [c[1] for c in sol.coordinates]
        assert abs(max(radii) - r0) / r0 < 1e-6


class TestTimeDilation:
    def test_velocity_dilation_06c(self):
        assert velocity_time_dilation(10.0, 0.6 * C) == pytest.approx(8.0, rel=1e-14)

    def test_velocity_dilation_low_speed_recovers_classical(self):
        assert velocity_time_dilation(10.0, 10.0) == pytest.approx(10.0, rel=1e-15)

    def test_velocity_dilation_accepts_vector3(self):
        assert velocity_time_dilation(10.0, Vector3(0.6 * C, 0.0, 0.0)) == pytest.approx(8.0)

    def test_velocity_dilation_rejects_superluminal(self):
        from astra.relativity.exceptions import LightSpeedViolation
        with pytest.raises(LightSpeedViolation):
            velocity_time_dilation(10.0, C)
        with pytest.raises(LightSpeedViolation):
            velocity_time_dilation(10.0, Vector3(C, C, 0.0))

    def test_gravitational_dilation_matches_weak_field(self):
        # dtau = dt * sqrt(1 - r_s/r); reuse check against the relativity API.
        m, r = 1.0e20, 1.0e9
        expected = 100.0 * math.sqrt(1.0 - schwarzschild_radius(m) / r)
        assert gravitational_time_dilation(100.0, m, r) == pytest.approx(expected, rel=1e-14)

    def test_gravitational_dilation_horizon_guard_inherited(self):
        # The RELATIVITY layer's DegenerateMetricError propagates (same
        # AstraError family, raised by the single weak-field implementation).
        from astra.relativity.exceptions import DegenerateMetricError
        from astra.core.exceptions import AstraError
        assert issubclass(DegenerateMetricError, AstraError)
        with pytest.raises(DegenerateMetricError):
            gravitational_time_dilation(10.0, MASS_SUN, schwarzschild_radius(MASS_SUN))

    def test_dilation_bad_time_inputs(self):
        from astra.temporal import InvalidTemporalStateError
        for bad in (-1.0, float("nan"), float("inf"), "x"):
            with pytest.raises(InvalidTemporalStateError):
                velocity_time_dilation(bad, 1.0)
            with pytest.raises(InvalidTemporalStateError):
                gravitational_time_dilation(bad, 1.0e20, 1.0e9)

    def test_determinism(self):
        vals = [
            (velocity_time_dilation(10.0, 0.5 * C),
             gravitational_time_dilation(10.0, 1.0e20, 1.0e9))
            for _ in range(500)
        ]
        assert all(v == vals[0] for v in vals)
