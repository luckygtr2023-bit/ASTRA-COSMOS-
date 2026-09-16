"""Timestep controller — explicit decisions, never silently clamped."""

import pytest

from astra.evolution.config import TimestepPolicy
from astra.evolution.timestep import AdaptiveTimestepController, TimestepReason
from astra.evolution.errors import EvolutionNumericalError


def test_timestep_never_silently_clamped_small_remaining():
    policy = TimestepPolicy(base_dt_gyr=0.1, min_dt_gyr=0.01, max_dt_gyr=1.0)
    ctrl = AdaptiveTimestepController(policy)
    # remaining smaller than min_dt must be returned as-is, not padded to min_dt
    d = ctrl.choose(remaining_gyr=0.005, model_id="toy")
    assert d.dt_gyr == pytest.approx(0.005)
    assert d.reason == TimestepReason.CONFIGURED_MIN
    assert "without clamping" in d.justification


def test_rate_limited_step():
    policy = TimestepPolicy(base_dt_gyr=1.0, min_dt_gyr=0.001, max_dt_gyr=1.0)
    ctrl = AdaptiveTimestepController(policy)
    d = ctrl.choose(remaining_gyr=10.0, rate_scale=10.0, model_id="toy")
    # base 1.0 / rate 10 = 0.1, bounded to [0.001,1.0]
    assert d.dt_gyr == pytest.approx(0.1)
    assert d.reason == TimestepReason.RATE_LIMITED


def test_event_driven_bounds():
    policy = TimestepPolicy(base_dt_gyr=1.0, min_dt_gyr=0.01, max_dt_gyr=1.0)
    ctrl = AdaptiveTimestepController(policy)
    d = ctrl.choose(remaining_gyr=10.0, next_event_gyr=0.05,
                    current_cosmic_time_gyr=0.0, model_id="toy")
    # event in 0.05 -> step should be 0.05 (directly to event)
    assert d.dt_gyr == pytest.approx(0.05)
    assert d.reason == TimestepReason.EVENT_DRIVEN


def test_zero_remaining():
    policy = TimestepPolicy(base_dt_gyr=0.1, min_dt_gyr=1e-4, max_dt_gyr=1.0)
    ctrl = AdaptiveTimestepController(policy)
    d = ctrl.choose(remaining_gyr=0.0, model_id="toy")
    assert d.dt_gyr == pytest.approx(0.0)


def test_negative_remaining_rejected():
    policy = TimestepPolicy(base_dt_gyr=0.1, min_dt_gyr=1e-4, max_dt_gyr=1.0)
    ctrl = AdaptiveTimestepController(policy)
    with pytest.raises(EvolutionNumericalError):
        ctrl.choose(remaining_gyr=-1.0, model_id="toy")


def test_nan_remaining_rejected():
    policy = TimestepPolicy(base_dt_gyr=0.1, min_dt_gyr=1e-4, max_dt_gyr=1.0)
    ctrl = AdaptiveTimestepController(policy)
    with pytest.raises(EvolutionNumericalError):
        ctrl.choose(remaining_gyr=float("nan"), model_id="toy")


def test_remaining_interval_reason():
    policy = TimestepPolicy(base_dt_gyr=10.0, min_dt_gyr=1e-4, max_dt_gyr=10.0)
    ctrl = AdaptiveTimestepController(policy)
    d = ctrl.choose(remaining_gyr=0.5, model_id="toy")
    assert d.dt_gyr == pytest.approx(0.5)
    assert d.reason == TimestepReason.REMAINING_INTERVAL


def test_policy_validation():
    with pytest.raises(ValueError):
        TimestepPolicy(min_dt_gyr=-1).validate()
    with pytest.raises(ValueError):
        TimestepPolicy(min_dt_gyr=1.0, max_dt_gyr=0.5).validate()
    with pytest.raises(ValueError):
        TimestepPolicy(base_dt_gyr=10.0, min_dt_gyr=0.01, max_dt_gyr=1.0).validate()
