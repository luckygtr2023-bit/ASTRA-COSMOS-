"""Wormhole model tests: admissibility, metric math, proper distance, ER bridge."""
import math

import pytest

from astra.spacetime import (
    DegenerateMetricError,
    InvalidCoordinateError,
    SchwarzschildMetric,
    christoffel_symbols,
)
from astra.spacetime.exceptions import DegenerateMetricError as STDegenerate
from astra.spacetime.geodesics import integrate_geodesic as integrate_chart
from astra.relativity.core import SPEED_OF_LIGHT as C
from astra.theoretical import (
    FlareOutViolation,
    InvalidGeometryParameterError,
    ScientificClassification,
    create_einstein_rosen_metric,
    create_morris_thorne_metric,
)

R0 = 10.0


def ellipsoid_b(r0):
    """b(r) = r0^2/r: b(r0)=r0, b'(r0)=-1<1 (admissible, rho<0 everywhere)."""
    return lambda r: r0 * r0 / r


class TestAdmissibility:
    def test_throat_condition_enforced(self):
        with pytest.raises(InvalidGeometryParameterError):
            create_morris_thorne_metric(R0, lambda r: 0.5 * R0)  # b(r0) != r0

    def test_flare_out_enforced(self):
        # b(r) = r0 + 2(r - r0): b'(r0) = 2 >= 1 -> flare-out violated.
        with pytest.raises(FlareOutViolation):
            create_morris_thorne_metric(R0, lambda r: R0 + 2.0 * (r - R0))

    def test_trapped_region_outside_rejected(self):
        # b(r) = r: b(r0)=r0 passes, b'(r0)=0<1 passes, but b(r)=r everywhere.
        with pytest.raises(InvalidGeometryParameterError):
            create_morris_thorne_metric(R0, lambda r: r)

    def test_non_callable_shape_rejected(self):
        with pytest.raises(InvalidGeometryParameterError):
            create_morris_thorne_metric(R0, 42)

    def test_bad_throat_radius_rejected(self):
        for bad in (0.0, -5.0, float("nan"), float("inf")):
            with pytest.raises(InvalidGeometryParameterError):
                create_morris_thorne_metric(bad, ellipsoid_b(1.0))


class TestMorrisThorneMetricMath:
    def test_components_at_known_point(self):
        mt = create_morris_thorne_metric(R0, ellipsoid_b(R0))
        r = 3.0 * R0
        g = mt.tensor((0.0, r, math.pi / 2, 0.1))
        b = R0 * R0 / r
        assert g[0][0] == pytest.approx(-1.0)  # Phi = 0
        assert g[1][1] == pytest.approx(1.0 / (1.0 - b / r))
        assert g[2][2] == pytest.approx(r * r)
        assert g[3][3] == pytest.approx(r * r)

    def test_symmetric_and_lorentzian(self):
        mt = create_morris_thorne_metric(R0, ellipsoid_b(R0))
        x = (0.0, 2.5 * R0, 0.9, 0.3)
        g = mt.tensor(x)
        for i in range(4):
            for j in range(4):
                assert g[i][j] == pytest.approx(g[j][i], rel=1e-14)
        assert g[0][0] < 0.0 and g[1][1] > 0.0 and g[2][2] > 0.0 and g[3][3] > 0.0

    @pytest.mark.parametrize("bad_r", [R0, R0 * 0.5, R0 - 1e-14, R0 - 1e-300,
                                       R0 + 1e-15, -1.0, 0.0])
    def test_throat_guard_band(self, bad_r):
        mt = create_morris_thorne_metric(R0, ellipsoid_b(R0))
        with pytest.raises((DegenerateMetricError, STDegenerate, InvalidCoordinateError)):
            mt.tensor((0.0, bad_r, math.pi / 2, 0.0))

    def test_christoffels_finite_far_from_throat(self):
        mt = create_morris_thorne_metric(R0, ellipsoid_b(R0))
        gamma = christoffel_symbols(mt, (0.0, 3.0 * R0, math.pi / 3, 0.2))
        worst = max(abs(gamma[a][b][c]) for a in range(4) for b in range(4)
                    for c in range(4))
        assert math.isfinite(worst) and worst < 1e6

    def test_infalling_geodesic_halted_at_throat(self):
        # From 20 r0 radially inward: the spacetime engine must halt with a
        # controlled error at the throat coordinate singularity.
        mt = create_morris_thorne_metric(R0, ellipsoid_b(R0))
        f = 1.0 - (R0 * R0 / (20 * R0)) / (20 * R0)
        u0 = C / math.sqrt(f)
        with pytest.raises(DegenerateMetricError):
            integrate_chart(mt, (0.0, 20.0 * R0, math.pi / 2, 0.0),
                            (u0, -0.3 * u0, 0.0, 0.0), 1e-4, steps=200)

    def test_proper_radial_distance_analytic(self):
        # For b = r0^2/r: l(r) = sqrt(r^2 - r0^2) EXACTLY.
        mt = create_morris_thorne_metric(R0, ellipsoid_b(R0))
        assert mt.proper_radial_distance(R0) == 0.0
        for mult in (1.5, 2.0, 4.0):
            r = mult * R0
            expected = math.sqrt(r * r - R0 * R0)
            assert mt.proper_radial_distance(r) == pytest.approx(expected, rel=1e-6)

    def test_proper_distance_monotonic_and_rejects_below(self):
        mt = create_morris_thorne_metric(R0, ellipsoid_b(R0))
        l1 = mt.proper_radial_distance(1.2 * R0)
        l2 = mt.proper_radial_distance(1.5 * R0)
        assert 0.0 < l1 < l2
        with pytest.raises(InvalidGeometryParameterError):
            mt.proper_radial_distance(0.5 * R0)

    def test_persistence_round_trip(self):
        mt = create_morris_thorne_metric(R0, ellipsoid_b(R0))
        restored = type(mt).from_dict(mt.to_dict(), ellipsoid_b(R0))
        assert restored.throat_radius_m == mt.throat_radius_m
        x = (0.0, 3 * R0, 0.5, 0.2)
        assert restored.tensor(x) == mt.tensor(x)


class TestEinsteinRosenBridge:
    def test_delegates_to_schwarzschild_exactly(self):
        er = create_einstein_rosen_metric(1.989e30)
        sm = SchwarzschildMetric(1.989e30)
        for x in ((0.0, 1e5, 0.7, 0.1), (5e6, 3.5 * sm.rs_m, math.pi / 3, 0.0)):
            assert er.tensor(x) == sm.tensor(x)

    def test_theoretical_and_non_traversable(self):
        er = create_einstein_rosen_metric(1.989e30)
        assert er.classification is ScientificClassification.THEORETICAL
        assert er.non_traversable is True

    def test_horizon_guard_inherited(self):
        er = create_einstein_rosen_metric(1.989e30)
        with pytest.raises(DegenerateMetricError):
            er.tensor((0.0, er.schwarzschild_delegate.rs_m, math.pi / 2, 0.0))

    def test_persistence_round_trip(self):
        er = create_einstein_rosen_metric(1.989e30)
        restored = type(er).from_dict(er.to_dict())
        x = (0.0, 1e5, 0.7, 0.1)
        assert restored.tensor(x) == er.tensor(x)
