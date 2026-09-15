"""Exotic-geometry causal analysis tests (analysis only - no execution)."""
import math
import os

import pytest

from astra.relativity.core import SPEED_OF_LIGHT as C
from astra.theoretical import (
    create_alcubierre_metric,
    create_morris_thorne_metric,
    create_white_hole_metric,
)
from astra.temporal import (
    ConeAnalysis,
    WhiteHoleTemporalCheck,
    WormholeChronologyDiagnostic,
    classify,
    relate,
    warp_cone_analysis,
    white_hole_temporal_check,
    wormhole_chronology_diagnostic,
)
from astra.temporal.exceptions import InvalidTemporalStateError


class TestWarpConeAnalysis:
    def test_flat_warp_zero_velocity_untitled_cone(self):
        w = create_alcubierre_metric(0.0, 100.0, 1.0)
        a = warp_cone_analysis(w, (0.0, 0.0, 0.0, 0.0))
        assert isinstance(a, ConeAnalysis)
        assert a.tilted_cone is False
        assert a.null_direction_count > 0

    def test_supercritical_bubble_tilts_cone(self):
        w = create_alcubierre_metric(5.0, 100.0, 1.0)
        center = warp_cone_analysis(w, (0.0, 0.0, 0.0, 0.0))
        assert center.tilted_cone is True
        assert center.null_direction_count >= 2
        # Null directions satisfy the metric's null condition exactly.
        for k in center.null_directions:
            ds2 = sum(w.tensor((0.0, 0.0, 0.0, 0.0))[a][b] * k[a] * k[b]
                      for a in range(4) for b in range(4))
            assert ds2 == pytest.approx(0.0, abs=1e-9)

    def test_far_field_cone_untilted(self):
        w = create_alcubierre_metric(5.0, 100.0, 1.0)
        a = warp_cone_analysis(w, (0.0, 1.0e5, 0.0, 0.0))
        assert a.tilted_cone is False

    def test_tilted_cone_classification_is_metric_driven(self):
        # A dx/dt = 0 worldline INSIDE a v_s = 5c bubble is spacelike
        # (reuses the validated tilted-cone physics from the prior phase).
        # Separations are METRE-SCALE so both events and their midpoint lie
        # inside the R = 100 m bubble (local_interval is midpoint-based).
        w = create_alcubierre_metric(5.0, 100.0, 1.0)
        c0 = (0.0, 0.0, 0.0, 0.0)
        assert classify(w, c0, (3.0, 0.0, 0.0, 0.0)).value == "SPACELIKE"
        # Comoving direction (dx = 5 dct inside the bubble) is timelike:
        assert classify(w, c0, (3.0, 15.0, 0.0, 0.0)).value == "TIMELIKE"

    def test_persistence_round_trip(self):
        w = create_alcubierre_metric(2.0, 50.0, 1.0)
        a = warp_cone_analysis(w, (0.0, 0.0, 0.0, 0.0))
        payload = a.to_dict()
        assert payload["tilted_cone"] is True


class TestWhiteHoleTemporalPolicy:
    def test_policy_delegated_not_bypassed(self):
        wh = create_white_hole_metric(1.989e30)
        rs = wh.rs_m
        x = (0.0, 1.2 * rs, math.pi / 2, 0.0)
        f = 1.0 - rs / (1.2 * rs)
        # Ingoing near-horizon: rejected THROUGH the existing policy.
        check = white_hole_temporal_check(wh, x, (C / math.sqrt(f), -100.0, 0.0, 0.0))
        assert isinstance(check, WhiteHoleTemporalCheck)
        assert check.allowed is False
        assert "emerge" in check.reason
        # Emergent: allowed.
        out = white_hole_temporal_check(wh, x, (C / math.sqrt(f), 100.0, 0.0, 0.0))
        assert out.allowed is True

    def test_spacelike_tangent_rejected_by_policy(self):
        wh = create_white_hole_metric(1.989e30)
        x = (0.0, 5.0 * wh.rs_m, math.pi / 2, 0.0)
        check = white_hole_temporal_check(wh, x, (0.0, 1.0, 0.0, 0.0))
        assert check.allowed is False

    def test_determinism(self):
        wh = create_white_hole_metric(1.989e30)
        rs = wh.rs_m
        x = (0.0, 1.2 * rs, math.pi / 2, 0.0)
        f = 1.0 - rs / (1.2 * rs)
        first = white_hole_temporal_check(wh, x, (C / math.sqrt(f), -1.0, 0.0, 0.0))
        for _ in range(500):
            assert white_hole_temporal_check(wh, x, (C / math.sqrt(f), -1.0, 0.0, 0.0)) == first


class TestWormholeChronology:
    def test_diagnostic_reports_no_ctc_in_single_patch(self):
        mt = create_morris_thorne_metric(10.0, lambda r: 100.0 / r)
        d = wormhole_chronology_diagnostic(mt, (10.0, 20.0, 40.0))
        assert isinstance(d, WormholeChronologyDiagnostic)
        assert d.chronology_violation_possible is False
        assert d.proper_throat_depth_at[0] == 0.0
        assert d.proper_throat_depth_at[1] == pytest.approx(math.sqrt(400.0 - 100.0),
                                                            rel=1e-6)
        assert "no time-travel execution API" in d.analysis

    def test_diagnostic_rejects_bad_radii(self):
        mt = create_morris_thorne_metric(10.0, lambda r: 100.0 / r)
        with pytest.raises(InvalidTemporalStateError):
            wormhole_chronology_diagnostic(mt, (float("nan"),))

    def test_analysis_not_execution_api(self):
        # The chronology surface is diagnostic-only: no traversal control.
        import astra.temporal as t
        public = [n for n in dir(t) if not n.startswith("_")]
        assert not any("travel" in n.lower() for n in public)


class TestNoForbiddenAPIs:
    def test_forbidden_time_travel_apis_absent_from_source(self):
        # Binding boundary (directive 24): no such API may be DEFINED.
        # (Docstrings naming the forbidden calls are the documented
        # boundary itself and are intentionally present.)
        import re
        import astra.temporal as pkg
        base = os.path.dirname(pkg.__file__)
        src = ""
        for fname in sorted(os.listdir(base)):
            if fname.endswith(".py"):
                with open(os.path.join(base, fname)) as fh:
                    src += fh.read()
        for forbidden in ("travel_to_past", "create_time_machine",
                          "rewrite_timeline", "reverse_causality",
                          "paradox_engine"):
            assert not re.search(rf"def\s+{forbidden}\b", src), forbidden
            assert not re.search(rf"\b{forbidden}\s*=", src), forbidden

    def test_ctc_mentioned_only_as_analysis_boundary(self):
        import astra.temporal as pkg
        base = os.path.dirname(pkg.__file__)
        src = ""
        for fname in sorted(os.listdir(base)):
            if fname.endswith(".py"):
                with open(os.path.join(base, fname)) as fh:
                    src += fh.read()
        # CTCs appear only in documentation/diagnostic strings.
        assert "chronology" in src.lower()
        assert "def generate_ctc" not in src
        assert "def create_ctc" not in src
