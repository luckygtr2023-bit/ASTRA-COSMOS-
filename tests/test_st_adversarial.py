"""Adversarial Spacetime tests: singular inputs, patch guards, determinism,
facade overspeed rejection, dependency hygiene."""
import math
import subprocess
import sys

import pytest

from astra.core.exceptions import AstraError
from astra.mathematics import Vector3
from astra.relativity.core import SPEED_OF_LIGHT as C
from astra.relativity.exceptions import LightSpeedViolation
from astra.spacetime import (
    DegenerateMetricError,
    GeodesicDivergenceError,
    HorizonCrossingError,
    InvalidCoordinateError,
    KerrMetric,
    MinkowskiMetric,
    NumericalMetric,
    SpacetimeError,
    SchwarzschildMetric,
    SpacetimeModel,
    calculate_christoffel,
    create_event,
    integrate_geodesic,
    kretschmann_scalar,
    ricci_scalar,
)

MASS_SUN = 1.989e30


class TestErrorHierarchy:
    def test_all_spacetime_errors_are_astra_errors(self):
        for exc in (SpacetimeError, InvalidCoordinateError, DegenerateMetricError,
                    HorizonCrossingError, GeodesicDivergenceError):
            assert issubclass(exc, AstraError)

    def test_validation_errors_are_value_errors(self):
        assert issubclass(InvalidCoordinateError, ValueError)


class TestMaliciousCoordinates:
    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    def test_non_finite_coordinate_slots_rejected(self, bad):
        sm = SchwarzschildMetric(MASS_SUN)
        for slot in range(4):
            coords = [0.0, 5 * sm.rs_m, math.pi / 3, 0.4]
            coords[slot] = bad
            with pytest.raises(InvalidCoordinateError):
                sm.tensor(coords)

    def test_negative_radius_rejected(self):
        sm = SchwarzschildMetric(MASS_SUN)
        with pytest.raises(DegenerateMetricError):
            sm.tensor((0.0, -1.0, math.pi / 2, 0.0))

    def test_axis_singularity_is_degenerate_metric(self):
        sm = SchwarzschildMetric(MASS_SUN)
        for theta in (0.0, math.pi, -0.1, math.pi + 0.1):
            with pytest.raises(DegenerateMetricError):
                sm.tensor((0.0, 10 * sm.rs_m, theta, 0.0))

    def test_kerr_axis_and_horizon(self):
        km = KerrMetric(MASS_SUN, 0.8)
        with pytest.raises(DegenerateMetricError):
            km.tensor((0.0, km.r_plus_m, math.pi / 2, 0.0))
        with pytest.raises(DegenerateMetricError):
            km.tensor((0.0, 10 * km.r_g, 0.0, 0.0))


class TestDegenerateMetrics:
    def test_user_field_singular(self):
        def singular(x):
            s = 1.0 if x[1] > 0 else 1.0
            return ((-s, 0, 0, 0), (0, s, 0, 0), (0, 0, s, 0), (0, 0, 0, 0.0))
        m = NumericalMetric(singular)
        with pytest.raises(DegenerateMetricError):
            m.inverse((0.0, 1.0, 0.0, 0.0))

    def test_connection_requires_invertible_metric(self):
        def singular(x):
            return ((-1.0, 0, 0, 0), (0, 1.0, 0, 0), (0, 0, 1.0, 0), (0, 0, 0, 0.0))
        m = NumericalMetric(singular)
        with pytest.raises(DegenerateMetricError):
            calculate_christoffel(m, (0.0, 1.0, 0.0, 0.0))


class TestGeodesicRobustness:
    def test_horizon_crossing_blocked_midstep(self):
        # Infalling geodesic with a huge step: the endpoint may leap past the
        # horizon; the stage/endpoint checks must still halt integration.
        sm = SchwarzschildMetric(MASS_SUN)
        rs = sm.rs_m
        r0 = 3.0 * rs
        f = 1.0 - rs / r0
        with pytest.raises(HorizonCrossingError):
            integrate_geodesic(
                sm, create_event(0.0, r0, 0.0, 0.0), Vector3(0.0, 0.0, 0.0),
                1.0, steps=5,
            )

    def test_massive_overspeed_rejected_everywhere(self):
        sm = SchwarzschildMetric(MASS_SUN)
        ev = create_event(0.0, 10 * sm.rs_m, 0.0, 0.0)
        with pytest.raises(LightSpeedViolation):
            integrate_geodesic(sm, ev, Vector3(C, C, 0.0), 1.0, steps=10)
        mm = MinkowskiMetric()
        with pytest.raises(LightSpeedViolation):
            integrate_geodesic(mm, create_event(0, 0, 0, 0), Vector3(C, C, 0.0),
                               1.0, steps=10)

    def test_worldline_strictly_increasing_parameters(self):
        sm = SchwarzschildMetric(MASS_SUN)
        rs = sm.rs_m
        ev = create_event(0.0, 8 * rs, 0.0, 0.0)
        omega = C * math.sqrt(rs / (2 * (8 * rs) ** 3))
        sol = integrate_geodesic(sm, ev, Vector3(0.0, 8 * rs * omega), 1e-3, steps=100)
        p = sol.parameters
        assert all(b > a for a, b in zip(p, p[1:]))


class TestDeterminism:
    def test_bit_for_bit_repetition(self):
        sm = SchwarzschildMetric(MASS_SUN)
        rs = sm.rs_m
        x = (0.0, 5 * rs, math.pi / 3, 0.4)

        def snapshot():
            return (
                sm.tensor(x),
                sm.inverse(x),
                sm.derivative(x),
                calculate_christoffel(sm, x),
                ricci_scalar(sm, x),
                kretschmann_scalar(sm, x),
            )

        first = snapshot()
        for _ in range(2000):
            assert snapshot() == first

    def test_geodesic_repetition(self):
        sm = SchwarzschildMetric(MASS_SUN)
        ev = create_event(0.0, 10 * sm.rs_m, 0.0, 0.0)
        omega = C * math.sqrt(sm.rs_m / (2 * (10 * sm.rs_m) ** 3))
        runs = [
            integrate_geodesic(sm, ev, Vector3(0.0, 10 * sm.rs_m * omega), 1e-4, steps=60)
            for _ in range(50)
        ]
        assert all(run == runs[0] for run in runs)


class TestDependencyHygiene:
    def test_no_reverse_dependency_from_blackhole(self):
        # BLACK-HOLE -> SPACETIME flow must be one-way: importing astra.blackhole
        # in a fresh interpreter must NOT pull in astra.spacetime.
        code = (
            "import sys; import astra.blackhole; "
            "print('astra.spacetime' in sys.modules)"
        )
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        assert out.returncode == 0
        assert out.stdout.strip() == "False"

    def test_spacetime_imports_relativity_and_blackhole(self):
        code = (
            "import sys; import astra.spacetime; "
            "print('astra.relativity' in sys.modules, "
            "'astra.blackhole' in sys.modules)"
        )
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        assert out.returncode == 0
        assert out.stdout.strip() == "True True"


class TestFacadeRobustness:
    def test_event_to_chart_round_trip(self):
        from astra.spacetime import event_to_chart, spherical_to_cartesian
        sm = SchwarzschildMetric(MASS_SUN)
        ev = create_event(0.0, 3.0, 4.0, 0.0)
        ct, r, theta, phi = event_to_chart(sm, ev)
        assert ct == 0.0
        assert r == pytest.approx(5.0)
        x, y, z = spherical_to_cartesian(r, theta, phi)
        assert x == pytest.approx(3.0)
        assert y == pytest.approx(4.0)

    def test_get_metric_tensor_kerr(self):
        g = SpacetimeModel.KERR
        from astra.spacetime import get_metric_tensor
        tensor = get_metric_tensor(g, (0.0, 1e5, math.pi / 2, 0.0),
                                   mass_kg=MASS_SUN, spin_param=0.4)
        assert tensor[0][3] != 0.0  # frame dragging cross-term present
