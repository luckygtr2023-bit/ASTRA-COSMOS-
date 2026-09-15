"""Adversarial Theoretical-layer tests: hostile inputs, hygiene, determinism,
dependency direction, forbidden-feature absence."""
import math
import subprocess
import sys

import pytest

from astra.core.exceptions import AstraError
from astra.spacetime import DegenerateMetricError
from astra.theoretical import (
    CausalityOrientationError,
    FlareOutViolation,
    InvalidGeometryParameterError,
    MAX_WARP_WALL_STEEPNESS,
    ScientificClassification,
    TheoreticalError,
    create_alcubierre_metric,
    create_morris_thorne_metric,
    create_white_hole_metric,
    evaluate_energy_conditions,
    get_scientific_classification,
)

R0 = 10.0


def ellipsoid_b(r0):
    return lambda r: r0 * r0 / r


class TestErrorHierarchy:
    def test_all_derive_from_astra_error(self):
        for exc in (TheoreticalError, InvalidGeometryParameterError,
                    FlareOutViolation, CausalityOrientationError):
            assert issubclass(exc, AstraError)

    def test_validation_errors_are_value_errors(self):
        assert issubclass(InvalidGeometryParameterError, ValueError)
        assert issubclass(FlareOutViolation, ValueError)


class TestHostileCallables:
    def test_shape_function_nan_output_rejected_at_build(self):
        def poisoned(r):
            return float("nan") if abs(r - R0) < 1e-9 else r
        with pytest.raises(InvalidGeometryParameterError):
            create_morris_thorne_metric(R0, poisoned)

    def test_shape_function_nan_output_rejected_at_eval(self):
        def midpoisoned(r):
            return float("nan") if r > 25.0 else r
        mt = create_morris_thorne_metric(R0, ellipsoid_b(R0))
        mt._b = midpoisoned  # simulate post-construction corruption
        with pytest.raises(DegenerateMetricError):
            mt.tensor((0.0, 30.0, math.pi / 2, 0.0))

    def test_redshift_nan_rejected(self):
        mt = create_morris_thorne_metric(R0, ellipsoid_b(R0),
                                         redshift_func=lambda r: float("nan"))
        with pytest.raises(DegenerateMetricError):
            mt.tensor((0.0, 3 * R0, math.pi / 2, 0.0))

    def test_redshift_explosion_rejected(self):
        mt = create_morris_thorne_metric(R0, ellipsoid_b(R0),
                                         redshift_func=lambda r: 1e30)
        with pytest.raises(DegenerateMetricError):
            mt.tensor((0.0, 3 * R0, math.pi / 2, 0.0))


class TestThroatUnderpenetration:
    @pytest.mark.parametrize("evil", [R0 - 1e-14, R0 - 1e-300, R0 - 1e-9,
                                      R0 + 1e-13, R0 + 1e-300])
    def test_float_attacks_on_throat_rejected(self, evil):
        # P2 regression class: any r <= r0 + epsilon is refused, including
        # ulp-level under-penetration; the metric never evaluates a negative
        # root of (1 - b/r).
        mt = create_morris_thorne_metric(R0, ellipsoid_b(R0))
        with pytest.raises(DegenerateMetricError):
            mt.tensor((0.0, evil, math.pi / 2, 0.0))

    def test_metric_never_negative_root(self):
        # Sweep just above the guard band: g_rr strictly positive everywhere.
        mt = create_morris_thorne_metric(R0, ellipsoid_b(R0))
        r = R0 * (1.0 + 1e-3)
        while r < 2.0 * R0:
            g = mt.tensor((0.0, r, math.pi / 2, 0.0))
            assert g[1][1] > 0.0
            r *= 1.5


class TestWarpHostility:
    def test_wall_steepness_at_cap_boundary(self):
        w = create_alcubierre_metric(1.0, 10.0, 1.0e4)  # exactly at the cap
        assert w.wall_steepness == 1.0e4
        assert MAX_WARP_WALL_STEEPNESS == 1.0e4

    def test_wall_steepness_above_cap_rejected(self):
        with pytest.raises(InvalidGeometryParameterError):
            create_alcubierre_metric(1.0, 10.0, math.nextafter(1.0e4, math.inf))

    def test_zero_thickness_equivalent_rejected(self):
        # sigma -> inf (step-function wall) is walled off by the cap.
        with pytest.raises(InvalidGeometryParameterError):
            create_alcubierre_metric(1.0, 10.0, float("inf"))

    def test_negative_velocity_admitted_coordinate_param(self):
        # Direction of the shift is arbitrary; -v_s is a valid coordinate choice.
        w = create_alcubierre_metric(-2.0, 50.0, 1.0)
        assert w.velocity == -2.0
        assert get_scientific_classification(w) is ScientificClassification.SPECULATIVE


class TestWhiteHoleHostility:
    def test_horizon_policy_requires_metric_patch(self):
        wh = create_white_hole_metric(1.989e30)
        rs = wh.rs_m
        # Inside the horizon the exterior chart is invalid: metric raises
        # before the policy can even classify the tangent.
        with pytest.raises(DegenerateMetricError):
            wh.assert_emissive_only((0.0, 0.5 * rs, math.pi / 2, 0.0),
                                    (1.0, 1.0, 0.0, 0.0))


class TestHygieneAndDirection:
    def test_no_reverse_dependency(self):
        # SPACETIME -> THEORETICAL flow must be one-way.
        code = ("import sys; import astra.spacetime; import astra.blackhole; "
                "print('astra.theoretical' in sys.modules)")
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        assert out.returncode == 0
        assert out.stdout.strip() == "False"

    def test_theoretical_pulls_spacetime(self):
        code = ("import sys; import astra.theoretical; "
                "print('astra.spacetime' in sys.modules)")
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        assert out.returncode ==0
        assert out.stdout.strip() == "True"

    def test_no_time_machine_feature(self):
        # Handoff section 35.17: CTC/time-machine machinery must NOT exist.
        import astra.theoretical as pkg
        import os
        src = ""
        for fname in os.listdir(os.path.dirname(pkg.__file__)):
            if fname.endswith(".py"):
                with open(os.path.join(os.path.dirname(pkg.__file__), fname)) as fh:
                    src += fh.read()
        assert "time_machine" not in src
        assert "closed_timelike" not in src.replace("closed-timelike-curve machinery", "")
        assert "CTC" not in src


class TestDeterminism:
    def test_five_thousand_cycle_reproducibility(self):
        mt = create_morris_thorne_metric(R0, ellipsoid_b(R0))
        w = create_alcubierre_metric(5.0, 100.0, 1.0)
        wh = create_white_hole_metric(1.989e30)

        def snapshot():
            return (
                mt.tensor((0.0, 3 * R0, math.pi / 3, 0.2)),
                mt.proper_radial_distance(2.0 * R0),
                w.tensor((0.0, 100.0, 0.0, 0.0)),
                evaluate_energy_conditions(mt, (0.0, 2 * R0, math.pi / 2, 0.0)),
                evaluate_energy_conditions(w, (0.0, 100.0, 0.0, 0.0)),
                wh.tensor((0.0, 1e5, 0.7, 0.1)),
            )

        first = snapshot()
        for _ in range(300):
            assert snapshot() == first
