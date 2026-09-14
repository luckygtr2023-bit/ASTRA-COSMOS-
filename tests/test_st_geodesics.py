"""Geodesic integration tests: flat limits, orbits, horizon guard, API."""
import math

import pytest

from astra.mathematics import Vector3
from astra.relativity.core import SPEED_OF_LIGHT as C
from astra.spacetime import (
    GeodesicDivergenceError,
    HorizonCrossingError,
    InvalidCoordinateError,
    MinkowskiMetric,
    SchwarzschildMetric,
    create_event,
    integrate_geodesic,
)
from astra.spacetime.geodesics import integrate_geodesic as integrate_chart

MASS_SUN = 1.989e30


def orbit_setup():
    """Exact Schwarzschild circular-orbit data at r = 10 r_s (equatorial)."""
    sm = SchwarzschildMetric(MASS_SUN)
    rs = sm.rs_m
    r0 = 10.0 * rs
    omega = C * math.sqrt(rs / (2.0 * r0 ** 3))
    gamma = 1.0 / math.sqrt(1.0 - 3.0 * rs / (2.0 * r0))
    return sm, rs, r0, omega, gamma


class TestFlatLimits:
    def test_massive_at_rest_is_inertial(self):
        sol = integrate_chart(MinkowskiMetric(), (0.0, 0.0, 0.0, 0.0), (C, 0, 0, 0),
                              1.0, steps=50)
        ct, x, y, z = sol.final_coordinates
        assert ct == pytest.approx(C, rel=1e-12)
        assert (x, y, z) == (0.0, 0.0, 0.0)

    def test_massive_straight_line(self):
        sol = integrate_chart(MinkowskiMetric(), (0.0, 0.0, 0.0, 0.0),
                              (C, 3.0, 4.0, 0.0), 2.0, steps=100)
        _, x, y, _ = sol.final_coordinates
        assert x == pytest.approx(6.0, rel=1e-12)
        assert y == pytest.approx(8.0, rel=1e-12)

    def test_null_ray_affine(self):
        sol = integrate_chart(MinkowskiMetric(), (0.0, 0.0, 0.0, 0.0),
                              (1.0, 1.0, 0.0, 0.0), 10.0, steps=100)
        ct, x, _, _ = sol.final_coordinates
        assert ct == pytest.approx(10.0)
        assert x == pytest.approx(10.0)

    def test_parameter_grid_is_uniform(self):
        sol = integrate_chart(MinkowskiMetric(), (0.0, 0.0, 0.0, 0.0), (C, 0, 0, 0),
                              1.0, steps=20)
        params = sol.parameters
        assert len(params) == 21
        for a, b in zip(params, params[1:]):
            assert b - a == pytest.approx(0.05, rel=1e-12)


class TestSchwarzschildOrbits:
    def test_circular_orbit_chart_native(self):
        sm, rs, r0, omega, gamma = orbit_setup()
        u = (gamma * C, 0.0, 0.0, gamma * omega)
        span = 2.0 * math.pi / (gamma * omega)  # two revolutions of proper time
        sol = integrate_chart(sm, (0.0, r0, math.pi / 2, 0.0), u, span, steps=4000)
        radii = [s[1] for s in sol.coordinates]
        assert abs(max(radii) - r0) / r0 < 1e-9
        assert abs(min(radii) - r0) / r0 < 1e-9

    def test_four_velocity_normalization_preserved(self):
        sm, rs, r0, omega, gamma = orbit_setup()
        u = (gamma * C, 0.0, 0.0, gamma * omega)
        sol = integrate_chart(sm, (0.0, r0, math.pi / 2, 0.0), u,
                              math.pi / (gamma * omega), steps=1000)
        uf = sol.four_velocities[-1]
        g = sm.tensor(sol.final_coordinates)
        norm = sum(g[a][b] * uf[a] * uf[b] for a in range(4) for b in range(4))
        assert norm == pytest.approx(-C * C, rel=1e-9)

    def test_facade_circular_orbit(self):
        sm, rs, r0, omega, gamma = orbit_setup()
        ev = create_event(0.0, r0, 0.0, 0.0)
        sol = integrate_geodesic(sm, ev, Vector3(0.0, r0 * omega, 0.0),
                                 2.0 * math.pi / (gamma * omega), steps=4000)
        radii = [s[1] for s in sol.coordinates]
        assert abs(max(radii) - r0) / r0 < 1e-8
        assert abs(min(radii) - r0) / r0 < 1e-8

    def test_facade_matches_chart_native(self):
        sm, rs, r0, omega, gamma = orbit_setup()
        ev = create_event(0.0, r0, 0.0, 0.0)
        sol_f = integrate_geodesic(sm, ev, Vector3(0.0, r0 * omega, 0.0), 0.1, steps=200)
        sol_c = integrate_chart(sm, (0.0, r0, math.pi / 2, 0.0),
                                (gamma * C, 0.0, 0.0, gamma * omega), 0.1, steps=200)
        assert sol_f.final_coordinates[1] == pytest.approx(sol_c.final_coordinates[1], rel=1e-12)
        assert sol_f.final_coordinates[3] == pytest.approx(sol_c.final_coordinates[3], rel=1e-12)

    def test_facade_null_ray_radial_escape(self):
        sm, rs, r0, omega, gamma = orbit_setup()
        ev = create_event(0.0, r0, 0.0, 0.0)
        sol = integrate_geodesic(sm, ev, Vector3(C, 0.0, 0.0), 5.0e-3, steps=250,
                                 massless=True)
        radii = [s[1] for s in sol.coordinates]
        assert radii[-1] > radii[0]
        assert all(b >= a for a, b in zip(radii, radii[1:]))  # monotonic escape

    def test_radial_infall_halts_at_horizon(self):
        sm, rs, r0, omega, gamma = orbit_setup()
        f = 1.0 - rs / r0
        with pytest.raises(HorizonCrossingError):
            integrate_chart(sm, (0.0, r0, math.pi / 2, 0.0),
                            (C / math.sqrt(f), 0.0, 0.0, 0.0), 10.0, steps=20000)

    def test_worldline_output(self):
        sm, rs, r0, omega, gamma = orbit_setup()
        u = (gamma * C, 0.0, 0.0, gamma * omega)
        sol = integrate_chart(sm, (0.0, r0, math.pi / 2, 0.0), u, 1e-3, steps=40)
        w = sol.to_worldline("spherical")
        assert len(w.samples) == 41
        params = w.parameters
        assert all(b > a for a, b in zip(params, params[1:]))
        assert w.final_event().chart == "spherical"


class TestIntegratorModes:
    def test_adaptive_agrees_with_fixed(self):
        sm, rs, r0, omega, gamma = orbit_setup()
        ev = create_event(0.0, r0, 0.0, 0.0)
        fixed = integrate_geodesic(sm, ev, Vector3(0.0, r0 * omega, 0.0),
                                   0.05, steps=800)
        adapt = integrate_geodesic(sm, ev, Vector3(0.0, r0 * omega, 0.0),
                                   0.05, steps=40, adaptive=True)
        # The astra.mathematics adaptive stepper bounds error against the
        # per-step |y| scale (u^0 ~ 1e9 m/s dominates), so cross-mode
        # agreement is honest at the 1e-6 relative level, not 1e-12.
        assert fixed.final_coordinates[1] == pytest.approx(
            adapt.final_coordinates[1], rel=1e-6
        )

    def test_fixed_step_determinism(self):
        sm, rs, r0, omega, gamma = orbit_setup()
        ev = create_event(0.0, r0, 0.0, 0.0)
        a = integrate_geodesic(sm, ev, Vector3(0.0, r0 * omega, 0.0), 1e-4, steps=100)
        b = integrate_geodesic(sm, ev, Vector3(0.0, r0 * omega, 0.0), 1e-4, steps=100)
        assert a == b  # bit-for-bit


class TestInputValidation:
    def test_bad_parameter_limit(self):
        m = MinkowskiMetric()
        for bad in (0.0, -1.0, float("nan"), float("inf")):
            with pytest.raises(InvalidCoordinateError):
                integrate_chart(m, (0.0, 0.0, 0.0, 0.0), (C, 0, 0, 0), bad, steps=10)

    def test_bad_steps(self):
        m = MinkowskiMetric()
        for bad in (0, -5, 10 ** 7):
            with pytest.raises(InvalidCoordinateError):
                integrate_chart(m, (0.0, 0.0, 0.0, 0.0), (C, 0, 0, 0), 1.0, steps=bad)

    def test_nan_initial_velocity_rejected(self):
        m = MinkowskiMetric()
        with pytest.raises(InvalidCoordinateError):
            integrate_chart(m, (0.0, 0.0, 0.0, 0.0),
                            (C, float("nan"), 0.0, 0.0), 1.0, steps=10)

    def test_velocity_inside_horizon_rejected(self):
        sm = SchwarzschildMetric(MASS_SUN)
        with pytest.raises(HorizonCrossingError):
            integrate_chart(sm, (0.0, sm.rs_m, math.pi / 2, 0.0),
                            (C, 0.0, 0.0, 0.0), 1e-3, steps=10)
