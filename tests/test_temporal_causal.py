"""Causal classification, ordering, and light-cone tests."""
import math

import pytest

from astra.relativity.core import SPEED_OF_LIGHT as C
from astra.spacetime import MinkowskiMetric, SchwarzschildMetric
from astra.spacetime.exceptions import InvalidCoordinateError
from astra.temporal import (
    CausalRelation,
    LightConeRegion,
    classify,
    cone_null_generators,
    is_causally_accessible,
    light_cone_region,
    relate,
)

MASS_SUN = 1.989e30


def _c(d):
    return tuple(float(v) for v in d)


class TestClassification:
    def test_anchor_timelike_null_spacelike(self):
        m = MinkowskiMetric()
        assert classify(m, (0, 0, 0, 0), (5 * C, 0, 0, 0)).value == "TIMELIKE"
        assert classify(m, (0, 0, 0, 0), (C, C, 0, 0)).value == "NULL"
        assert classify(m, (0, 0, 0, 0), (0, C, 0, 0)).value == "SPACELIKE"

    def test_zero_interval_is_null(self):
        # Zero separation classifies consistently with the ASTRA convention
        # (ds^2 = 0 band) and relate() reports COINCIDENT for exact equality.
        m = MinkowskiMetric()
        assert classify(m, (1.0, 2.0, 3.0, 4.0), (1.0, 2.0, 3.0, 4.0)).value == "NULL"
        assert relate(m, (1.0, 2.0, 3.0, 4.0), (1.0, 2.0, 3.0, 4.0)) is (
            CausalRelation.COINCIDENT
        )

    def test_near_null_numerical_cases(self):
        m = MinkowskiMetric()
        # ds^2 = -(1+1e-12)c^2 + ... engineered within the tolerance band.
        d = (C * (1.0 + 5e-13), C, 0.0, 0.0)
        assert classify(m, (0, 0, 0, 0), d, tolerance=1e-9 * C * C).value == "NULL"

    def test_large_values(self):
        m = MinkowskiMetric()
        big = 1.0e18  # ~3e9 years of light travel
        assert classify(m, (0, 0, 0, 0), (2 * big, 0.5 * big, 0, 0)).value == "TIMELIKE"

    def test_tiny_values_with_explicit_tolerance(self):
        # attosecond-scale separations sit BELOW the default tolerance band
        # (documented NULL-by-tolerance behavior); an explicit tighter
        # tolerance classifies them TIMELIKE - explicit tolerances are the
        # contract, never silent conversion.
        m = MinkowskiMetric()
        tiny = 1.0e-18
        assert classify(m, (0, 0, 0, 0), (2 * tiny * C, 0, 0, 0)).value == "NULL"
        assert classify(m, (0, 0, 0, 0), (2 * tiny * C, 0, 0, 0),
                        tolerance=1e-40).value == "TIMELIKE"

    @pytest.mark.parametrize("bad", [float("nan"), float("inf")])
    def test_nan_inf_rejected(self, bad):
        m = MinkowskiMetric()
        with pytest.raises(InvalidCoordinateError):
            classify(m, (0, 0, 0, 0), (bad, 0.0, 0.0, 0.0))
        with pytest.raises(InvalidCoordinateError):
            relate(m, (bad, 0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0))

    def test_metric_driven_classification_schwarzschild(self):
        # Classification uses the ACTIVE metric: radial null at r = 10 r_s.
        # local_interval evaluates g at the MIDPOINT (documented
        # linearization), so the null condition uses f(r_mid).
        sm = SchwarzschildMetric(MASS_SUN)
        rs = sm.rs_m
        base = (rs, 10.0 * rs, math.pi / 2, 0.0)
        # dr = 1 m keeps the analytic null's FP cancellation residue
        # (~dr^2 * 1e-15) far inside the default 1e-9 m^2 tolerance band.
        dr = 1.0
        f_mid = 1.0 - rs / (10.0 * rs + 0.5 * dr)
        dct = dr / f_mid  # radial null: -f dct^2 + dr^2/f = 0 -> dct = dr/f
        assert classify(sm, base, (base[0] + dct, base[1] + dr,
                                   base[2], base[3])).value == "NULL"


class TestCausalOrdering:
    def test_precedes_relations(self):
        m = MinkowskiMetric()
        a = (0.0, 0.0, 0.0, 0.0)
        b = (5.0 * C, 1.0, 0.0, 0.0)
        assert relate(m, a, b) is CausalRelation.A_PRECEDES_B
        assert relate(m, b, a) is CausalRelation.B_PRECEDES_A

    def test_null_separation_is_ordered(self):
        # Null-ordered events: all frames agree B follows A.
        m = MinkowskiMetric()
        assert relate(m, (0, 0, 0, 0), (C, C, 0, 0)) is CausalRelation.A_PRECEDES_B
        assert relate(m, (C, C, 0, 0), (0, 0, 0, 0)) is CausalRelation.B_PRECEDES_A

    def test_spacelike_never_ordered(self):
        # Binding design rule: no arbitrary total order on spacelike pairs.
        m = MinkowskiMetric()
        a = (0.0, 0.0, 0.0, 0.0)
        b = (0.0, 10.0 * C, 0.0, 0.0)
        assert relate(m, a, b) is CausalRelation.CAUSALLY_DISCONNECTED
        assert relate(m, b, a) is CausalRelation.CAUSALLY_DISCONNECTED

    def test_spacelike_ordering_symmetric_in_time_order(self):
        # Even when one coordinate time is later, spacelike stays disconnected.
        m = MinkowskiMetric()
        a = (5.0 * C, 0.0, 0.0, 0.0)
        b = (6.0 * C, 100.0 * C, 0.0, 0.0)
        assert relate(m, a, b) is CausalRelation.CAUSALLY_DISCONNECTED

    def test_coincident(self):
        m = MinkowskiMetric()
        x = (1.0, -2.0, 3.0, 4.0)
        assert relate(m, x, x) is CausalRelation.COINCIDENT


class TestLightCones:
    def test_regions(self):
        m = MinkowskiMetric()
        a = (0.0, 0.0, 0.0, 0.0)
        assert light_cone_region(m, a, (2 * C, 0.5 * C, 0, 0)) is (
            LightConeRegion.INSIDE_FUTURE_CONE)
        assert light_cone_region(m, a, (C, C, 0, 0)) is LightConeRegion.ON_FUTURE_CONE
        assert light_cone_region(m, a, (-2 * C, 0.5 * C, 0, 0)) is (
            LightConeRegion.INSIDE_PAST_CONE)
        assert light_cone_region(m, a, (-C, -C, 0, 0)) is LightConeRegion.ON_PAST_CONE
        assert light_cone_region(m, a, (0.0, 5 * C, 0, 0)) is (
            LightConeRegion.SPACELIKE_EXTERIOR)
        assert light_cone_region(m, a, a) is LightConeRegion.COINCIDENT

    def test_accessibility_anchor(self):
        m = MinkowskiMetric()
        # Subluminal future signal: accessible. Spacelike: never.
        assert is_causally_accessible(m, (0, 0, 0, 0), (2 * C, C, 0, 0)) is True
        assert is_causally_accessible(m, (0, 0, 0, 0), (0, C, 0, 0)) is False
        # Past cone is not "following A".
        assert is_causally_accessible(m, (2 * C, 0, 0, 0), (0, 0, 0, 0)) is False

    def test_no_ftl_accessibility_exists(self):
        # The API surface cannot express faster-than-light reachability.
        import astra.temporal as t
        public = [n for n in dir(t) if not n.startswith("_")]
        assert not any("ftl" in n.lower() or "superluminal" in n.lower() for n in public)

    def test_cone_null_generators_diagonal(self):
        m = MinkowskiMetric()
        (future, past), = cone_null_generators(m, (0, 0, 0, 0), ((1.0, 0.0, 0.0),))
        assert future[0] > 0.0 and past[0] < 0.0
        # Null check on the generator itself.
        assert classify(m, (0, 0, 0, 0), future).value == "NULL"
        assert classify(m, (0, 0, 0, 0), past).value == "NULL"

    def test_determinism(self):
        m = MinkowskiMetric()
        pairs = [((0, 0, 0, 0), (k * C, 0.5 * k * C, 0.1 * k * C, 0.0))
                 for k in (0.5, 1.0, 1.5, 2.0)]
        first = [relate(m, a, b) for a, b in pairs]
        for _ in range(1000):
            assert [relate(m, a, b) for a, b in pairs] == first
