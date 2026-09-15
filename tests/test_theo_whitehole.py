"""White hole tests: exterior identity, emissive-only causal policy."""
import math

import pytest

from astra.relativity.core import SPEED_OF_LIGHT as C
from astra.spacetime import SchwarzschildMetric
from astra.theoretical import (
    CausalityOrientationError,
    InvalidGeometryParameterError,
    ScientificClassification,
    create_white_hole_metric,
)

MASS_SUN = 1.989e30


class TestExteriorIdentity:
    def test_tensor_identical_to_schwarzschild(self):
        wh = create_white_hole_metric(MASS_SUN)
        sm = SchwarzschildMetric(MASS_SUN)
        for x in ((0.0, 1e5, 0.7, 0.1), (1e9, 2.5 * sm.rs_m, math.pi / 4, -0.2)):
            assert wh.tensor(x) == sm.tensor(x)

    def test_classification_theoretical(self):
        assert create_white_hole_metric(MASS_SUN).classification is (
            ScientificClassification.THEORETICAL
        )

    def test_bad_mass_rejected(self):
        for bad in (0.0, -1.0, float("nan"), float("inf"), "sun"):
            with pytest.raises((InvalidGeometryParameterError)):
                create_white_hole_metric(bad)

    def test_persistence_round_trip(self):
        wh = create_white_hole_metric(MASS_SUN)
        restored = type(wh).from_dict(wh.to_dict())
        x = (0.0, 1e5, 0.7, 0.1)
        assert restored.tensor(x) == wh.tensor(x)


class TestEmissiveOnlyPolicy:
    def test_ingoing_near_horizon_blocked(self):
        wh = create_white_hole_metric(MASS_SUN)
        rs = wh.rs_m
        x = (0.0, 1.2 * rs, math.pi / 2, 0.0)
        u_in = (C / math.sqrt(1.0 - rs / (1.2 * rs)), -100.0, 0.0, 0.0)
        with pytest.raises(CausalityOrientationError):
            wh.assert_emissive_only(x, u_in)

    def test_emergent_near_horizon_allowed(self):
        wh = create_white_hole_metric(MASS_SUN)
        rs = wh.rs_m
        x = (0.0, 1.2 * rs, math.pi / 2, 0.0)
        u_out = (C / math.sqrt(1.0 - rs / (1.2 * rs)), 100.0, 0.0, 0.0)
        wh.assert_emissive_only(x, u_out)  # no raise

    def test_ingoing_far_from_horizon_allowed(self):
        # Policy band is local: distant infall is ordinary approach, not
        # penetration of the emission barrier.
        wh = create_white_hole_metric(MASS_SUN)
        rs = wh.rs_m
        x = (0.0, 10.0 * rs, math.pi / 2, 0.0)
        u_in = (C / math.sqrt(1.0 - rs / (10.0 * rs)), -1e4, 0.0, 0.0)
        wh.assert_emissive_only(x, u_in)  # no raise

    def test_spacelike_tangent_blocked(self):
        wh = create_white_hole_metric(MASS_SUN)
        x = (0.0, 5.0 * wh.rs_m, math.pi / 2, 0.0)
        # Pure radial "velocity" with vanishing time slot: spacelike.
        with pytest.raises(CausalityOrientationError):
            wh.assert_emissive_only(x, (0.0, 1.0, 0.0, 0.0))

    def test_null_tangent_accepted(self):
        wh = create_white_hole_metric(MASS_SUN)
        x = (0.0, 3.0 * wh.rs_m, math.pi / 2, 0.0)
        f = 1.0 - wh.rs_m / (3.0 * wh.rs_m)
        # Outgoing null ray: u^0/u^r = sqrt(g_rr / (-g_00)) -> null.
        ratio = math.sqrt((1.0 / f) / f)
        wh.assert_emissive_only(x, (ratio, 1.0, 0.0, 0.0))  # no raise

    def test_nan_velocity_rejected(self):
        wh = create_white_hole_metric(MASS_SUN)
        x = (0.0, 3.0 * wh.rs_m, math.pi / 2, 0.0)
        with pytest.raises(InvalidGeometryParameterError):
            wh.assert_emissive_only(x, (float("nan"), 1.0, 0.0, 0.0))

    def test_bad_velocity_shape_rejected(self):
        wh = create_white_hole_metric(MASS_SUN)
        x = (0.0, 3.0 * wh.rs_m, math.pi / 2, 0.0)
        with pytest.raises(InvalidGeometryParameterError):
            wh.assert_emissive_only(x, (1.0, 2.0, 3.0))
