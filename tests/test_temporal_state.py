"""Temporal state, interval, and clock tests (incl. authority)."""
import dataclasses
import math
import threading

import pytest

from astra.core.exceptions import AuthorityError
from astra.core.threading import (
    AuthorityContext,
    get_simulation_thread_registry,
    reset_simulation_thread_registry,
)
from astra.temporal import (
    InvalidTemporalStateError,
    TemporalClock,
    TemporalInterval,
    TemporalState,
)


@pytest.fixture(autouse=True)
def sim_thread():
    reset_simulation_thread_registry()
    get_simulation_thread_registry().register_simulation_thread(
        threading.current_thread().ident
    )
    yield
    reset_simulation_thread_registry()


class TestTemporalState:
    def test_explicit_fields(self):
        s = TemporalState(simulation_time_s=10.0, coordinate_time_s=10.0,
                          proper_time_s=8.0, observer="probe-1", rate=0.8)
        assert (s.simulation_time_s, s.coordinate_time_s, s.proper_time_s) == (10.0, 10.0, 8.0)
        assert s.rate == 0.8

    def test_elapsed_interval(self):
        a = TemporalState(0.0, 0.0, 0.0, "probe-1")
        b = TemporalState(10.0, 10.0, 8.0, "probe-1", 0.8)
        iv = b.elapsed_since(a)
        assert isinstance(iv, TemporalInterval)
        assert iv.simulation_delta_s == pytest.approx(10.0)
        assert iv.proper_delta_s == pytest.approx(8.0)

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1.0, "10", True])
    def test_invalid_times_rejected(self, bad):
        with pytest.raises(InvalidTemporalStateError):
            TemporalState(bad, 0.0, 0.0, "o")

    def test_bad_rate_rejected(self):
        for bad in (0.0, -0.5, float("nan"), float("inf")):
            with pytest.raises(InvalidTemporalStateError):
                TemporalState(0.0, 0.0, 0.0, "o", rate=bad)

    def test_bad_observer_rejected(self):
        for bad in ("", None, 42):
            with pytest.raises(InvalidTemporalStateError):
                TemporalState(0.0, 0.0, 0.0, bad)

    def test_frozen(self):
        s = TemporalState(1.0, 1.0, 1.0, "o")
        with pytest.raises(dataclasses.FrozenInstanceError):
            s.simulation_time_s = 99.0

    def test_persistence_round_trip(self):
        s = TemporalState(12.5, 12.5, 9.75, "probe-9", 0.78)
        assert TemporalState.from_dict(s.to_dict()) == s

    def test_from_dict_rejects_corruption(self):
        payload = TemporalState(1.0, 1.0, 1.0, "o").to_dict()
        payload["rate"] = "fast"
        with pytest.raises(InvalidTemporalStateError):
            TemporalState.from_dict(payload)
        payload2 = TemporalState(1.0, 1.0, 1.0, "o").to_dict()
        del payload2["proper_time_s"]
        with pytest.raises(KeyError):
            TemporalState.from_dict(payload2)


class TestTemporalClock:
    def test_explicit_advance_only(self):
        clock = TemporalClock("engine")
        with AuthorityContext("temporal"):
            clock.advance(5.0)
            clock.advance(2.5)
        s = clock.to_state()
        assert s.simulation_time_s == pytest.approx(7.5)
        assert s.coordinate_time_s == pytest.approx(7.5)
        assert s.proper_time_s == pytest.approx(7.5)  # rate 1.0 default

    def test_rate_accumulates_proper_time(self):
        clock = TemporalClock("engine")
        with AuthorityContext("temporal"):
            clock.set_rate(0.6)
            clock.advance(10.0)
        assert clock.proper_time_s == pytest.approx(6.0)
        assert clock.coordinate_time_s == pytest.approx(10.0)

    def test_no_wall_clock_advance_without_call(self):
        # Identical call sequences -> bit-identical states (no hidden time).
        a = TemporalClock("engine")
        b = TemporalClock("engine")
        with AuthorityContext("temporal"):
            a.advance(3.25)
            b.advance(3.25)
        assert a.to_state() == b.to_state()

    def test_advance_requires_authority(self):
        clock = TemporalClock("engine")
        with pytest.raises(AuthorityError):
            clock.advance(1.0)

    def test_set_rate_requires_authority(self):
        clock = TemporalClock("engine")
        with pytest.raises(AuthorityError):
            clock.set_rate(0.5)

    def test_reset_requires_authority(self):
        clock = TemporalClock("engine")
        with pytest.raises(AuthorityError):
            clock.reset()

    def test_non_simulation_thread_cannot_advance(self):
        clock = TemporalClock("engine")
        errors = []

        def intruder():
            try:
                with AuthorityContext("temporal"):
                    clock.advance(1.0)
            except AuthorityError as exc:
                errors.append(exc)

        t = threading.Thread(target=intruder)
        t.start()
        t.join(timeout=5.0)
        assert errors, "non-simulation thread must be denied authority"
        assert clock.simulation_time_s == 0.0

    def test_negative_and_nan_dt_rejected(self):
        clock = TemporalClock("engine")
        with AuthorityContext("temporal"):
            for bad in (-1.0, float("nan"), float("inf"), True):
                with pytest.raises(InvalidTemporalStateError):
                    clock.advance(bad)
        assert clock.simulation_time_s == 0.0

    def test_determinism(self):
        states = []
        for _ in range(500):
            c = TemporalClock("engine")
            with AuthorityContext("temporal"):
                c.set_rate(0.7)
                c.advance(1.0)
                c.advance(0.5)
            states.append(c.to_state())
        assert all(s == states[0] for s in states)
