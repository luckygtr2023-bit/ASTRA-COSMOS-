import math
import pytest
from astra.mathematics import Vector3
from astra.orbital import (
    OrbitalState, propagate, state_to_elements, elements_to_state,
    orbital_period, solve_kepler_elliptic, solve_kepler_hyperbolic,
    solve_barker,
    true_to_eccentric, eccentric_to_true,
    true_to_mean_elliptic, mean_to_true_elliptic,
    KeplerConvergenceError,
    vis_viva, circular_velocity, escape_velocity,
)


MU_EARTH = 3.986004418e14


def _circular(r: float) -> OrbitalState:
    v = math.sqrt(MU_EARTH / r)
    return OrbitalState(position=Vector3(r, 0, 0),
                        velocity=Vector3(0, v, 0), mu=MU_EARTH)


class TestKepler:
    def test_elliptic_roundtrip(self):
        for M in (0.0, 0.5, 1.0, 2.0, 3.0, -1.0):
            for e in (0.0, 0.1, 0.5, 0.9):
                E = solve_kepler_elliptic(M, e)
                M2 = E - e * math.sin(E)
                assert abs(M2 - M) < 1e-10

    def test_hyperbolic_roundtrip(self):
        for M in (-5.0, -1.0, 0.0, 1.0, 5.0):
            for e in (1.1, 1.5, 3.0):
                H = solve_kepler_hyperbolic(M, e)
                M2 = e * math.sinh(H) - H
                assert abs(M2 - M) < 1e-9

    def test_barker(self):
        for M in (-3.0, -1.0, 0.0, 1.0, 3.0):
            D = solve_barker(M)
            M2 = D + D ** 3 / 3.0
            assert abs(M2 - M) < 1e-10

    def test_elliptic_invalid_e(self):
        with pytest.raises(Exception):
            solve_kepler_elliptic(0.5, 1.5)


class TestAnomalies:
    def test_true_eccentric_roundtrip(self):
        for nu in (0.1, 0.5, 1.0, 2.0, -0.5):
            for e in (0.1, 0.5, 0.9):
                E = true_to_eccentric(nu, e)
                nu2 = eccentric_to_true(E, e)
                assert abs(nu2 - nu) < 1e-9

    def test_mean_roundtrip(self):
        for nu in (0.1, 1.0, 2.0):
            for e in (0.1, 0.5):
                M = true_to_mean_elliptic(nu, e)
                nu2 = mean_to_true_elliptic(M, e)
                assert abs(nu2 - nu) < 1e-9


class TestPropagate:
    def test_circular_period(self):
        r = 7.0e6
        s = _circular(r)
        T = orbital_period(r, MU_EARTH)
        s2 = propagate(s, T)
        assert s2.position.distance_to(s.position) / r < 1e-6
        assert s2.velocity.distance_to(s.velocity) / math.sqrt(MU_EARTH / r) < 1e-6

    def test_elliptic_energy_conserved(self):
        r_p, r_a = 1.0e7, 3.0e7
        a = 0.5 * (r_p + r_a)
        v_p = math.sqrt(MU_EARTH * (2.0 / r_p - 1.0 / a))
        s = OrbitalState(position=Vector3(r_p, 0, 0),
                         velocity=Vector3(0, v_p, 0), mu=MU_EARTH)
        eps0 = 0.5 * s.v ** 2 - s.mu / s.r
        for _ in range(20):
            s = propagate(s, 1000.0)
            eps = 0.5 * s.v ** 2 - s.mu / s.r
            assert abs(eps - eps0) / abs(eps0) < 1e-9

    def test_angular_momentum_conserved(self):
        r_p, r_a = 1.0e7, 3.0e7
        a = 0.5 * (r_p + r_a)
        v_p = math.sqrt(MU_EARTH * (2.0 / r_p - 1.0 / a))
        s = OrbitalState(position=Vector3(r_p, 0, 0),
                         velocity=Vector3(0, v_p, 0), mu=MU_EARTH)
        h0 = s.position.cross(s.velocity)
        for _ in range(20):
            s = propagate(s, 500.0)
            h = s.position.cross(s.velocity)
            assert h.distance_to(h0) / h0.magnitude() < 1e-9

    def test_zero_dt(self):
        s = _circular(7.0e6)
        s2 = propagate(s, 0.0)
        assert s2.position == s.position
        assert s2.velocity == s.velocity

    def test_backward(self):
        s = _circular(7.0e6)
        s_fwd = propagate(s, 100.0)
        s_back = propagate(s_fwd, -100.0)
        assert s_back.position.distance_to(s.position) / 7.0e6 < 1e-6

    def test_deterministic(self):
        s = _circular(7.0e6)
        a = propagate(s, 1234.5)
        b = propagate(s, 1234.5)
        assert a.position == b.position
        assert a.velocity == b.velocity


class TestVelocities:
    def test_vis_viva_circular(self):
        r = 7.0e6
        vc = circular_velocity(r, MU_EARTH)
        v = vis_viva(r, r, MU_EARTH)
        assert abs(v - vc) / vc < 1e-12

    def test_escape(self):
        r = 7.0e6
        v_esc = escape_velocity(r, MU_EARTH)
        assert abs(v_esc / circular_velocity(r, MU_EARTH) - math.sqrt(2)) < 1e-12
