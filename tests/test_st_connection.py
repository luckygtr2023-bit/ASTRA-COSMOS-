"""Christoffel symbol tests against hand-derived Schwarzschild tables."""
import math

import pytest

from astra.spacetime import (
    MinkowskiMetric,
    SchwarzschildMetric,
    christoffel_symbols,
)

MASS_SUN = 1.989e30


class TestMinkowskiConnection:
    def test_flat_spacetime_has_zero_connection(self):
        m = MinkowskiMetric()
        for x in ((0.0, 0.0, 0.0, 0.0), (5.0, 1.0, -2.0, 3.0)):
            gamma = christoffel_symbols(m, x)
            for rho in range(4):
                for mu in range(4):
                    for nu in range(4):
                        assert gamma[rho][mu][nu] == 0.0


class TestSchwarzschildConnection:
    def test_hand_derived_values(self):
        sm = SchwarzschildMetric(MASS_SUN)
        rs = sm.rs_m
        r = 5.0 * rs
        theta = math.pi / 3
        gamma = christoffel_symbols(sm, (0.0, r, theta, 0.4))
        # Gamma^r_tt = r_s (r - r_s) / (2 r^3)
        assert gamma[1][0][0] == pytest.approx(rs * (r - rs) / (2.0 * r ** 3), rel=1e-12)
        # Gamma^r_thth = -(r - r_s)
        assert gamma[1][2][2] == pytest.approx(-(r - rs), rel=1e-12)
        # Gamma^r_phph = -(r - r_s) sin^2(theta)
        assert gamma[1][3][3] == pytest.approx(-(r - rs) * math.sin(theta) ** 2, rel=1e-12)
        # Gamma^th_rth = Gamma^ph_rph = 1/r
        assert gamma[2][1][2] == pytest.approx(1.0 / r, rel=1e-12)
        assert gamma[3][1][3] == pytest.approx(1.0 / r, rel=1e-12)
        # Gamma^th_phph = -sin(theta) cos(theta)
        assert gamma[2][3][3] == pytest.approx(
            -math.sin(theta) * math.cos(theta), rel=1e-12
        )
        # Gamma^ph_thph = cot(theta)
        assert gamma[3][2][3] == pytest.approx(1.0 / math.tan(theta), rel=1e-12)
        # Gamma^r_rr = -r_s / (2 r^2 f) with f = 1 - r_s/r (negative: metric
        # flattens outward, g_rr decreasing).
        f = 1.0 - rs / r
        assert gamma[1][1][1] == pytest.approx(-rs / (2.0 * r * r * f), rel=1e-12)
        # Gamma^t_tr = Gamma^r_tt / (c^2 f^2 / ...) - direct form: r_s/(2 r^2 f)
        assert gamma[0][0][1] == pytest.approx(rs / (2.0 * r * r * f), rel=1e-12)

    def test_symmetry_in_lower_indices(self):
        sm = SchwarzschildMetric(MASS_SUN)
        gamma = christoffel_symbols(sm, (0.0, 5 * sm.rs_m, math.pi / 3, 0.4))
        for rho in range(4):
            for mu in range(4):
                for nu in range(4):
                    assert gamma[rho][mu][nu] == pytest.approx(gamma[rho][nu][mu], rel=1e-12)

    def test_time_independence(self):
        sm = SchwarzschildMetric(MASS_SUN)
        g1 = christoffel_symbols(sm, (0.0, 5 * sm.rs_m, math.pi / 4, 0.2))
        g2 = christoffel_symbols(sm, (1e7, 5 * sm.rs_m, math.pi / 4, 0.2))
        assert g1 == g2  # static metric: bit-identical

    def test_kerr_zero_spin_matches_schwarzschild(self):
        from astra.spacetime import KerrMetric
        km = KerrMetric(MASS_SUN, 0.0)
        sm = SchwarzschildMetric(MASS_SUN)
        x = (0.0, 5 * sm.rs_m, math.pi / 3, 0.4)
        gk = christoffel_symbols(km, x)
        gs = christoffel_symbols(sm, x)
        for rho in range(4):
            for mu in range(4):
                for nu in range(4):
                    # Kerr's numeric derivative path carries absolute FD
                    # cancellation noise (~6e-4) on components whose field
                    # neighbors are O(1e4); relative-to-field ~1e-10.
                    assert gk[rho][mu][nu] == pytest.approx(
                        gs[rho][mu][nu], rel=1e-6, abs=1e-2
                    )

    def test_horizon_guard(self):
        sm = SchwarzschildMetric(MASS_SUN)
        with pytest.raises(Exception):
            christoffel_symbols(sm, (0.0, sm.rs_m, math.pi / 2, 0.0))
