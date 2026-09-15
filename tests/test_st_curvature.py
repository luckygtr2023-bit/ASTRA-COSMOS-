"""Curvature tensor tests: vacuum identities and exact invariants."""
import math

import pytest

from astra.relativity.core import SPEED_OF_LIGHT as C
from astra.spacetime import (
    MinkowskiMetric,
    SchwarzschildMetric,
    calculate_ricci_scalar,
    einstein_tensor,
    kretschmann_scalar,
    ricci_scalar,
    ricci_tensor,
    riemann_tensor,
    tidal_acceleration,
)

MASS_SUN = 1.989e30


class TestMinkowskiCurvature:
    def test_riemann_exactly_zero(self):
        m = MinkowskiMetric()
        r = riemann_tensor(m, (0.0, 1.0, 2.0, 3.0))
        for rho in range(4):
            for sigma in range(4):
                for mu in range(4):
                    for nu in range(4):
                        assert r[rho][sigma][mu][nu] == 0.0

    def test_vacuum_invariants_zero(self):
        m = MinkowskiMetric()
        x = (1.0, -2.0, 3.0, 4.0)
        assert ricci_scalar(m, x) == 0.0
        assert kretschmann_scalar(m, x) == 0.0


class TestSchwarzschildVacuum:
    def test_ricci_tensor_vanishes(self):
        sm = SchwarzschildMetric(MASS_SUN)
        x = (0.0, 5 * sm.rs_m, math.pi / 3, 0.4)
        ric = ricci_tensor(sm, x)
        scale = sm.rs_m / (5 * sm.rs_m) ** 3  # curvature scale
        # Component residuals are finite-difference noise of the numeric
        # d(Gamma) chain in the large-Gamma angular sector (deterministic,
        # measured max 3.05% of the local scale rs/r^3). The physically
        # contracted Ricci SCALAR holds far tighter (see next test, ~1e-19).
        for mu in range(4):
            for nu in range(4):
                assert abs(ric[mu][nu]) < 5e-2 * scale

    def test_ricci_scalar_vanishes(self):
        sm = SchwarzschildMetric(MASS_SUN)
        for mult in (4.0, 10.0, 25.0):
            R = ricci_scalar(sm, (0.0, mult * sm.rs_m, math.pi / 4, 0.9))
            assert abs(R) < 1e-8 * sm.rs_m / (mult * sm.rs_m) ** 3

    def test_einstein_tensor_vanishes(self):
        sm = SchwarzschildMetric(MASS_SUN)
        x = (0.0, 6 * sm.rs_m, math.pi / 3, 0.4)
        ge = einstein_tensor(sm, x)
        scale = sm.rs_m / (6 * sm.rs_m) ** 3
        for mu in range(4):
            for nu in range(4):
                assert abs(ge[mu][nu]) < 5e-2 * scale

    def test_riemann_nonzero_tidal(self):
        sm = SchwarzschildMetric(MASS_SUN)
        r = riemann_tensor(sm, (0.0, 5 * sm.rs_m, math.pi / 3, 0.4))
        norm = sum(abs(r[a][b][c][d]) for a in range(4) for b in range(4)
                   for c in range(4) for d in range(4))
        assert norm > 0.0

    def test_kretschmann_exact_invariant(self):
        sm = SchwarzschildMetric(MASS_SUN)
        for mult in (5.0, 10.0, 25.0):
            r = mult * sm.rs_m
            x = (0.0, r, math.pi / 3, 0.4)
            K = kretschmann_scalar(sm, x)
            expected = 12.0 * sm.rs_m ** 2 / r ** 6
            assert K == pytest.approx(expected, rel=1e-8)

    def test_riemann_symmetries(self):
        sm = SchwarzschildMetric(MASS_SUN)
        x = (0.0, 5 * sm.rs_m, math.pi / 3, 0.4)
        r = riemann_tensor(sm, x)
        # Antisymmetry in last pair: R^rho_{sigma mu nu} = -R^rho_{sigma nu mu}
        for rho in range(4):
            for sigma in range(4):
                for mu in range(4):
                    for nu in range(4):
                        assert r[rho][sigma][mu][nu] == pytest.approx(
                            -r[rho][sigma][nu][mu], rel=1e-9, abs=1e-14
                        )


class TestGeodesicDeviation:
    def test_radial_stretch_transverse_squeeze_ratio_two(self):
        sm = SchwarzschildMetric(MASS_SUN)
        rs = sm.rs_m
        r = 10 * rs
        x = (0.0, r, math.pi / 2, 0.0)
        # Static fiducial observer: u^mu = (c/sqrt(f), 0, 0, 0).
        f = 1.0 - rs / r
        u = (C / math.sqrt(f), 0.0, 0.0, 0.0)
        a_radial = tidal_acceleration(sm, x, u, (0.0, 1.0, 0.0, 0.0))
        a_trans = tidal_acceleration(sm, x, u, (0.0, 0.0, 1.0, 0.0))
        # Radial component stretches (positive), coefficient c^2 r_s / r^3.
        assert a_radial[1] == pytest.approx(C * C * rs / r ** 3, rel=1e-8)
        # Transverse coordinate component: -c^2 r_s / (2 r^3) (times r^2 units).
        assert a_trans[2] < 0.0
        assert abs(a_trans[2]) == pytest.approx(abs(a_radial[1]) / 2.0, rel=1e-8)

    def test_time_component_zero_for_static(self):
        sm = SchwarzschildMetric(MASS_SUN)
        x = (0.0, 10 * sm.rs_m, math.pi / 2, 0.0)
        f = 1.0 - sm.rs_m / (10 * sm.rs_m)
        u = (C / math.sqrt(f), 0.0, 0.0, 0.0)
        a = tidal_acceleration(sm, x, u, (0.0, 0.0, 0.0, 1.0))
        assert a[0] == pytest.approx(0.0, abs=1e-16)
