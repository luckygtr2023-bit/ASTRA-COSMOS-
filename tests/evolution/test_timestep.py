"""Phase 21 — timestep controller tests (spec 2.31): explicit decisions,
no silent clamping."""
from __future__ import annotations

import math

import pytest

from astra.evolution import (
    AdaptiveTimestepController,
    EvolutionNumericalError,
    TimestepPolicy,
    TimestepReason,
)


def _controller(**policy):
    return AdaptiveTimestepController(TimestepPolicy(**policy))


def test_policy_ceiling_applied():
    d = _controller().choose(
        now_gyr=0.0, remaining_gyr=100.0, rate_scale=0.0,
        next_event_time_gyr=None, model_id="m",
    )
    assert d.dt_gyr == pytest.approx(1.0)
    assert d.reason is TimestepReason.CONFIGURED_MAX
    assert d.clamped_to_remaining is False


def test_rate_limited_shortens_steps():
    d = _controller(base_dt_gyr=0.1).choose(
        now_gyr=0.0, remaining_gyr=100.0, rate_scale=10.0,
        next_event_time_gyr=None, model_id="m",
    )
    assert d.dt_gyr == pytest.approx(0.01)
    assert d.reason is TimestepReason.RATE_LIMITED


def test_rate_floor_is_recorded_not_silent():
    d = _controller(base_dt_gyr=0.1, min_dt_gyr=0.05).choose(
        now_gyr=0.0, remaining_gyr=100.0, rate_scale=1.0e6,
        next_event_time_gyr=None, model_id="m",
    )
    assert d.dt_gyr == pytest.approx(0.05)
    assert d.reason is TimestepReason.RATE_LIMITED
    assert "floor" in d.justification


def test_event_boundary_lands_exactly():
    d = _controller().choose(
        now_gyr=0.0, remaining_gyr=100.0, rate_scale=0.0,
        next_event_time_gyr=0.37, model_id="m",
    )
    assert d.dt_gyr == pytest.approx(0.37)
    assert d.reason is TimestepReason.EVENT_DRIVEN
    assert d.clamped_to_remaining is False


def test_event_never_stepped_past():
    d = _controller(max_dt_gyr=10.0).choose(
        now_gyr=5.0, remaining_gyr=95.0, rate_scale=0.0,
        next_event_time_gyr=6.0, model_id="m",
    )
    assert d.dt_gyr == pytest.approx(1.0)
    assert 5.0 + d.dt_gyr == pytest.approx(6.0)


def test_remainder_below_min_dt_is_explicit():
    d = _controller(min_dt_gyr=0.01).choose(
        now_gyr=0.0, remaining_gyr=0.005, rate_scale=0.0,
        next_event_time_gyr=None, model_id="m",
    )
    assert d.dt_gyr == pytest.approx(0.005)
    assert d.reason is TimestepReason.REMAINDER
    assert "not clamped" in d.justification
    assert d.clamped_to_remaining is True


def test_rate_limited_never_exceeds_ceiling():
    """Decaying rate_scale must lengthen steps only UP TO max_dt_gyr —
    never silently past the declared ceiling."""
    for rate in (1.0, 0.1, 0.01, 1e-4, 1e-8):
        d = _controller(base_dt_gyr=1.0, max_dt_gyr=10.0).choose(
            now_gyr=0.0, remaining_gyr=1000.0, rate_scale=rate,
            next_event_time_gyr=None, model_id="m",
        )
        assert d.dt_gyr <= 10.0 + 1e-12, f"rate={rate}: dt {d.dt_gyr} exceeded ceiling"
        if rate < 0.1:
            assert "ceiling" in d.justification


def test_covering_remaining_records_requested_dt():
    d = _controller().choose(
        now_gyr=0.0, remaining_gyr=0.5, rate_scale=0.0,
        next_event_time_gyr=None, model_id="m",
    )
    assert d.dt_gyr == pytest.approx(0.5)
    assert d.clamped_to_remaining is True
    assert d.requested_dt_gyr == pytest.approx(1.0)  # what the policy wanted
    assert d.reason is TimestepReason.CONFIGURED_MAX


def test_zero_remaining_is_no_interval():
    d = _controller().choose(
        now_gyr=0.0, remaining_gyr=0.0, rate_scale=0.0,
        next_event_time_gyr=None, model_id="m",
    )
    assert d.dt_gyr == 0.0
    assert d.reason is TimestepReason.NO_INTERVAL


@pytest.mark.parametrize("bad", [-1.0, float("nan"), float("inf")])
def test_invalid_remaining_rejected(bad):
    with pytest.raises(EvolutionNumericalError):
        _controller().choose(
            now_gyr=0.0, remaining_gyr=bad, rate_scale=0.0,
            next_event_time_gyr=None, model_id="m",
        )


def test_event_in_the_past_rejected():
    with pytest.raises(EvolutionNumericalError):
        _controller().choose(
            now_gyr=5.0, remaining_gyr=10.0, rate_scale=0.0,
            next_event_time_gyr=4.0, model_id="m",
        )


def test_event_driven_disabled_refuses_scheduled_events():
    ctrl = _controller(allow_event_driven=False)
    with pytest.raises(EvolutionNumericalError):
        ctrl.choose(
            now_gyr=0.0, remaining_gyr=10.0, rate_scale=0.0,
            next_event_time_gyr=1.0, model_id="m",
        )


def test_policy_validated():
    with pytest.raises(Exception):
        TimestepPolicy(min_dt_gyr=0.0)
    with pytest.raises(Exception):
        TimestepPolicy(min_dt_gyr=1.0, max_dt_gyr=0.5)
    with pytest.raises(Exception):
        TimestepPolicy(base_dt_gyr=10.0, min_dt_gyr=0.1, max_dt_gyr=1.0)


def test_decision_serialization_round_trip():
    d = _controller().choose(
        now_gyr=0.0, remaining_gyr=100.0, rate_scale=5.0,
        next_event_time_gyr=None, model_id="m",
    )
    d2 = __import__(
        "astra.evolution.timestep", fromlist=["TimestepDecision"]
    ).TimestepDecision.from_dict(d.to_dict())
    assert d2 == d
