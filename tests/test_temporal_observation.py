"""Observation-vs-actual-state and lookback tests (directive section 22 anchor)."""
import math

import pytest

from astra.relativity.core import SPEED_OF_LIGHT as C
from astra.spacetime import SpacetimeEvent, Worldline
from astra.spacetime.events import CHART_CARTESIAN
from astra.temporal import (
    InvalidTemporalStateError,
    InvalidWorldlineError,
    ObservedState,
    TemporalHistoryUnavailableError,
    lookback_time,
    observe,
)

LS = C  # one light-second in metres


def _static_history(t_start: float, t_end: float, x: float, y: float = 0.0,
                    z: float = 0.0, steps: int = 31):
    samples = []
    for i in range(steps):
        t = t_start + (t_end - t_start) * i / (steps - 1)
        samples.append((t, SpacetimeEvent.from_coordinates(t, x, y, z, CHART_CARTESIAN)))
    return Worldline(tuple(samples))


class TestDirectiveAnchor:
    def test_object_at_100s_observed_at_110s(self):
        # Object static 10 light-seconds away; history recorded 90..120 s.
        # Observation at t = 110 s must see the EMISSION state of t = 100 s
        # (delay = 10 s), while the actual state at 110 s stays 110 s.
        history = _static_history(90.0, 120.0, 10.0 * LS)
        obs = observe(history, (0.0, 0.0, 0.0), 110.0, "earth")
        assert isinstance(obs, ObservedState)
        assert obs.lookback_time_s == pytest.approx(10.0, rel=1e-9)
        assert obs.emission_time_s == pytest.approx(100.0, rel=1e-9)
        assert obs.emission_event.time_sec == pytest.approx(100.0, rel=1e-9)
        # ACTUAL state unchanged by observation:
        assert obs.actual_state_at_observation.time_sec == pytest.approx(110.0, rel=1e-12)
        # And the recorded history itself was never mutated:
        assert history.events[0].time_sec == pytest.approx(90.0)

    def test_moving_object_retardation(self):
        # Observer 10 ls away; object rests at x=0 until t=20 s, then moves
        # toward the observer at 0.5c. Observing at t=35: null path requires
        # t_e + (10 - x(t_e)) = 35 with x(t) = 0.5(t - 20) for t >= 20
        # -> 0.5 t_e + 20 = 35 -> t_e = 30 s, x = 2.5 ls, delay 5 s.
        samples = []
        for i in range(61):
            t = 0.0 + 40.0 * i / 60.0
            x = 0.0 if t < 20.0 else (t - 20.0) * 0.5 * LS
            samples.append((t, SpacetimeEvent.from_coordinates(t, x, 0.0, 0.0,
                                                              CHART_CARTESIAN)))
        history = Worldline(tuple(samples))
        obs = observe(history, (10.0 * LS, 0.0, 0.0), 35.0, "base")
        assert obs.emission_time_s == pytest.approx(30.0, abs=1e-6)
        assert obs.lookback_time_s == pytest.approx(5.0, abs=1e-6)
        assert obs.emission_event.x == pytest.approx(5.0 * LS, rel=1e-6)
        assert obs.actual_state_at_observation.time_sec == pytest.approx(35.0)

    def test_observed_state_type_and_persistence(self):
        history = _static_history(90.0, 120.0, 10.0 * LS)
        obs = observe(history, (0.0, 0.0, 0.0), 110.0, "earth")
        restored = ObservedState.from_dict(obs.to_dict())
        assert restored == obs


class TestNoFabricatedHistory:
    def test_emission_before_record_rejected(self):
        # History starts at 90 s; a distant enough observer needs earlier
        # emission: explicit failure, no invention.
        history = _static_history(90.0, 120.0, 100.0 * LS)  # 100 ls away
        with pytest.raises(TemporalHistoryUnavailableError):
            observe(history, (0.0, 0.0, 0.0), 110.0, "earth")

    def test_observation_time_inside_history_required(self):
        history = _static_history(90.0, 120.0, 10.0 * LS)
        with pytest.raises(TemporalHistoryUnavailableError):
            observe(history, (0.0, 0.0, 0.0), 200.0, "earth")

    def test_light_not_yet_arrived(self):
        # Emission at first sample has not reached the observer by t_obs.
        history = _static_history(105.0, 120.0, 10.0 * LS)  # emitted 105, arrives 115
        with pytest.raises(TemporalHistoryUnavailableError):
            observe(history, (0.0, 0.0, 0.0), 110.0, "earth")

    def test_interpolation_strictly_between_samples(self):
        # Emission between two recorded samples is interpolated - and only
        # then; the answer is bounded by the recorded values.
        history = _static_history(90.0, 120.0, 10.0 * LS, steps=7)  # 5 s cadence
        obs = observe(history, (0.0, 0.0, 0.0), 112.0, "earth")
        assert 90.0 <= obs.emission_time_s <= 120.0
        assert obs.emission_event.time_sec == pytest.approx(102.0, abs=1e-6)


class TestGeometricLookback:
    def test_static_geometry(self):
        lb = lookback_time((0.0, 0.0, 0.0), (10.0 * LS, 0.0, 0.0), 110.0, 100.0)
        assert lb == pytest.approx(10.0, rel=1e-15)

    def test_diagonal_geometry(self):
        d = (3.0 * LS, 4.0 * LS, 0.0)
        lb = lookback_time((0.0, 0.0, 0.0), d, 110.0, 100.0)
        assert lb == pytest.approx(5.0, rel=1e-15)

    def test_emission_after_observation_rejected(self):
        with pytest.raises(InvalidTemporalStateError):
            lookback_time((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), 100.0, 110.0)

    def test_nan_positions_rejected(self):
        with pytest.raises(InvalidTemporalStateError):
            lookback_time((float("nan"), 0.0, 0.0), (1.0, 0.0, 0.0), 110.0, 100.0)


class TestInputValidation:
    def test_history_shape(self):
        one = Worldline(((0.0, SpacetimeEvent(0, 0, 0, 0)),))
        with pytest.raises(InvalidWorldlineError):
            observe(one, (0.0, 0.0, 0.0), 1.0)
        with pytest.raises(InvalidWorldlineError):
            observe("not-a-worldline", (0.0, 0.0, 0.0), 1.0)

    def test_bad_observer_inputs(self):
        history = _static_history(0.0, 20.0, LS)
        with pytest.raises(InvalidTemporalStateError):
            observe(history, (0.0, 0.0), 10.0)
        with pytest.raises(InvalidTemporalStateError):
            observe(history, (0.0, 0.0, 0.0), -5.0)
        with pytest.raises(InvalidTemporalStateError):
            observe(history, (0.0, 0.0, 0.0), 10.0, "")

    def test_determinism(self):
        history = _static_history(90.0, 120.0, 10.0 * LS, steps=61)
        first = observe(history, (0.0, 0.0, 0.0), 110.0, "earth")
        for _ in range(300):
            assert observe(history, (0.0, 0.0, 0.0), 110.0, "earth") == first
