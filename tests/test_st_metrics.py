"""Metric field tests: components, determinants, inverses, model limits."""
import math

import pytest

from astra.relativity.core import SPEED_OF_LIGHT as C
from astra.spacetime import (
    DegenerateMetricError,
    InvalidCoordinateError,
    KerrMetric,
    MinkowskiMetric,
    NumericalMetric,
    SchwarzschildMetric,
    SpacetimeModel,
    get_metric_tensor,
)

MASS_SUN = 1.989e30


def mat_mul(a, b):
    return tuple(
        tuple(sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)) for i in range(4)
    )


class TestMinkowskiMetric:
    def test_signature_everywhere(self):
        m = MinkowskiMetric()
        for x in ((0.0, 0.0, 0.0, 0.0), (1e9, -5.0, 3.0, 2.0), (-1e12, 1.0, 2.0, 3.0)):
            g = m.tensor(x)
            assert g == ((-1.0, 0, 0, 0), (0, 1.0, 0, 0), (0, 0, 1.0, 0), (0, 0, 0, 1.0))
            assert m.determinant(x) == pytest.approx(-1.0)
            assert m.inverse(x) == g  # inverse of diag(-1,1,1,1) is itself

    def test_model_enum(self):
        assert MinkowskiMetric().model is SpacetimeModel.MINKOWSKI

    def test_nan_coords_rejected(self):
        with pytest.raises(InvalidCoordinateError):
            MinkowskiMetric().tensor((0.0, float("nan"), 0.0, 0.0))

    def test_wrong_shape_rejected(self):
        with pytest.raises(InvalidCoordinateError):
            MinkowskiMetric().tensor((0.0, 1.0, 2.0))


class TestSchwarzschildMetric:
    def test_components_at_known_point(self):
        sm = SchwarzschildMetric(MASS_SUN)
        rs = sm.rs_m
        r = 5.0 * rs
        g = sm.tensor((0.0, r, math.pi / 3, 0.4))
        f = 1.0 - 1.0 / 5.0
        assert g[0][0] == pytest.approx(-f)
        assert g[1][1] == pytest.approx(1.0 / f)
        assert g[2][2] == pytest.approx(r * r)
        assert g[3][3] == pytest.approx(r * r * 0.75)  # sin^2(pi/3)
        for i in range(4):
            for j in range(4):
                if i != j:
                    assert g[i][j] == 0.0

    def test_determinant(self):
        sm = SchwarzschildMetric(MASS_SUN)
        rs = sm.rs_m
        r, theta = 5.0 * rs, 0.7
        assert sm.determinant((0.0, r, theta, 0.1)) == pytest.approx(
            -(r ** 4) * math.sin(theta) ** 2, rel=1e-12
        )

    def test_inverse_unity(self):
        sm = SchwarzschildMetric(MASS_SUN)
        x = (0.0, 5.0 * sm.rs_m, math.pi / 3, 0.4)
        g, gi = sm.tensor(x), sm.inverse(x)
        ident = mat_mul(g, gi)
        for i in range(4):
            for j in range(4):
                assert ident[i][j] == pytest.approx(1.0 if i == j else 0.0, rel=1e-9, abs=1e-9)

    def test_inverse_hand_values(self):
        sm = SchwarzschildMetric(MASS_SUN)
        x = (0.0, 5.0 * sm.rs_m, math.pi / 2, 0.0)
        gi = sm.inverse(x)
        assert gi[0][0] == pytest.approx(-1.25)
        assert gi[1][1] == pytest.approx(0.8)
        assert gi[2][2] == pytest.approx(1.0 / (5.0 * sm.rs_m) ** 2)

    def test_horizon_guard(self):
        sm = SchwarzschildMetric(MASS_SUN)
        rs = sm.rs_m
        for r in (rs, 0.5 * rs, rs - 1e-6):
            with pytest.raises(DegenerateMetricError):
                sm.tensor((0.0, r, math.pi / 2, 0.0))

    def test_axis_guard(self):
        sm = SchwarzschildMetric(MASS_SUN)
        for theta in (0.0, math.pi):
            with pytest.raises(DegenerateMetricError):
                sm.tensor((0.0, 10.0 * sm.rs_m, theta, 0.0))

    def test_r_s_from_blackhole_layer(self):
        from astra.blackhole.schwarzschild import schwarzschild_radius_m
        sm = SchwarzschildMetric(MASS_SUN)
        assert sm.rs_m == schwarzschild_radius_m(MASS_SUN)

    def test_analytic_derivative_vs_numeric(self):
        sm = SchwarzschildMetric(MASS_SUN)
        x = (0.0, 5.0 * sm.rs_m, math.pi / 3, 0.4)
        da = sm.derivative(x)
        dn = reference_derivative_numeric(sm, x)
        nonzero = 0
        for a in range(4):
            for mu in range(4):
                for nu in range(4):
                    if da[a][mu][nu] == 0.0:
                        # Analytic zeros are exact (metric separable in coords).
                        assert da[a][mu][nu] == 0.0
                    else:
                        nonzero += 1
                        # Nonzero partials agree with 4th-order reference to
                        # truncation/roundoff level of the reference itself.
                        assert da[a][mu][nu] == pytest.approx(
                            dn[a][mu][nu], rel=1e-6
                        )
        assert nonzero == 5  # dr: g_tt, g_rr, g_thth, g_phph; dtheta: g_phph


def reference_derivative_numeric(metric, x):
    """Reference 4th-order central differences (independent of the class)."""
    h_base = 1.0e-5
    out = []
    for a in range(4):
        h = h_base * max(abs(x[a]), 1.0)

        def g_at(off):
            xp = list(x)
            xp[a] += off
            return metric.tensor(xp)

        gp, gm = g_at(h), g_at(-h)
        g2p, g2m = g_at(2 * h), g_at(-2 * h)
        plane = []
        for mu in range(4):
            row = []
            for nu in range(4):
                row.append(
                    (-g2p[mu][nu] + 8 * gp[mu][nu] - 8 * gm[mu][nu] + g2m[mu][nu]) / (12 * h)
                )
            plane.append(tuple(row))
        out.append(tuple(plane))
    return tuple(out)


class TestKerrMetric:
    def test_zero_spin_equals_schwarzschild(self):
        km = KerrMetric(MASS_SUN, 0.0)
        sm = SchwarzschildMetric(MASS_SUN)
        for x in ((0.0, 10 * sm.rs_m, math.pi / 2, 0.1),
                  (1e5, 3.7 * sm.rs_m, math.pi / 4, -0.3)):
            gk, gs = km.tensor(x), sm.tensor(x)
            for i in range(4):
                for j in range(4):
                    assert gk[i][j] == pytest.approx(gs[i][j], rel=1e-14, abs=1e-14)

    def test_determinant_formula(self):
        km = KerrMetric(MASS_SUN, 0.5)
        rg, a = km.r_g, km.a
        for (r, theta) in ((10 * rg, math.pi / 3), (5 * rg, 2 * math.pi / 3)):
            det = km.determinant((0.0, r, theta, 0.2))
            sigma = r * r + a * a * math.cos(theta) ** 2
            expected = -(sigma ** 2) * math.sin(theta) ** 2
            assert det == pytest.approx(expected, rel=1e-12)

    def test_g00_independent_of_spin_at_equator(self):
        # g_tt = -(1 - 2 r_g r / Sigma) with Sigma = r^2 at the equator.
        km = KerrMetric(MASS_SUN, 0.9)
        rg = km.r_g
        g = km.tensor((0.0, 8 * rg, math.pi / 2, 0.0))
        assert g[0][0] == pytest.approx(-(1.0 - 2.0 / 8.0))

    def test_horizon_guard(self):
        km = KerrMetric(MASS_SUN, 0.6)
        with pytest.raises(DegenerateMetricError):
            km.tensor((0.0, km.r_plus_m, math.pi / 2, 0.0))
        with pytest.raises(DegenerateMetricError):
            km.tensor((0.0, 0.5 * km.r_plus_m, math.pi / 2, 0.0))

    def test_invalid_spin_propagates(self):
        from astra.blackhole import InvalidSpinParameterError
        with pytest.raises(InvalidSpinParameterError):
            KerrMetric(MASS_SUN, 1.5)


class TestNumericalMetric:
    def test_flat_field_reproduces_minkowski(self):
        m = NumericalMetric(lambda x: ((-1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)))
        x = (1.0, 2.0, 3.0, 4.0)
        assert m.tensor(x) == MinkowskiMetric().tensor(x)
        d = m.derivative(x)
        for a in range(4):
            for mu in range(4):
                for nu in range(4):
                    assert abs(d[a][mu][nu]) < 1e-9

    def test_nan_field_rejected(self):
        def bad(x):
            row = [0.0] * 4
            row[0] = float("nan")
            return ((row[0], 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))
        with pytest.raises(InvalidCoordinateError):
            NumericalMetric(bad).tensor((0.0, 0.0, 0.0, 0.0))

    def test_singular_field_raises_on_inverse(self):
        def rank_deficient(x):
            return ((1.0, 0, 0, 0), (0, 1.0, 0, 0), (0, 0, 1.0, 0), (0, 0, 0, 0.0))
        m = NumericalMetric(rank_deficient)
        with pytest.raises(DegenerateMetricError):
            m.inverse((0.0, 0.0, 0.0, 0.0))

    def test_non_callable_rejected(self):
        with pytest.raises(InvalidCoordinateError):
            NumericalMetric(42)


class TestFacadeDispatch:
    def test_get_metric_tensor(self):
        g = get_metric_tensor(SpacetimeModel.MINKOWSKI, (0.0, 1.0, 2.0, 3.0))
        assert g[0][0] == -1.0
        g2 = get_metric_tensor(SpacetimeModel.SCHWARZSCHILD, (0.0, 1e5, 0.5, 0.0),
                               mass_kg=MASS_SUN)
        rs = SchwarzschildMetric(MASS_SUN).rs_m
        assert g2[0][0] == pytest.approx(-(1.0 - rs / 1e5), rel=1e-12)
