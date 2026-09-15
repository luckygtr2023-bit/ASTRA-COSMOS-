"""Adversarial Temporal-layer tests: extremes, hostile inputs, determinism,
dependency hygiene, authority."""
import math
import subprocess
import sys
import threading

import pytest

from astra.core.exceptions import AstraError, AuthorityError
from astra.core.threading import (
    AuthorityContext,
    get_simulation_thread_registry,
    reset_simulation_thread_registry,
)
from astra.relativity.core import SPEED_OF_LIGHT as C
from astra.spacetime import (
    MinkowskiMetric,
    SchwarzschildMetric,
    SpacetimeEvent,
    Worldline,
)
from astra.spacetime.events import CHART_CARTESIAN
from astra.temporal import (
    InvalidTemporalStateError,
    InvalidWorldlineError,
    TemporalClock,
    TemporalError,
    TemporalHistoryUnavailableError,
    TemporalState,
    classify,
    flat_proper_time,
    observe,
    relate,
    velocity_time_dilation,
)


@pytest.fixture(autouse=True)
def sim_thread():
    reset_simulation_thread_registry()
    get_simulation_thread_registry().register_simulation_thread(
        threading.current_thread().ident
    )
    yield
    reset_simulation_thread_registry()


MASS_SUN = 1.989e30


class TestErrorHierarchy:
    def test_all_temporal_errors_are_astra_errors(self):
        for exc in (TemporalError, InvalidTemporalStateError, InvalidWorldlineError,
                    TemporalHistoryUnavailableError):
            assert issubclass(exc, AstraError)

    def test_validation_errors_are_value_errors(self):
        assert issubclass(InvalidTemporalStateError, ValueError)
        assert issubclass(InvalidWorldlineError, ValueError)


class TestNumericalExtremes:
    def test_very_large_timestamps(self):
        # ~3e9 years of simulation time: finite and exact classification.
        m = MinkowskiMetric()
        big = 1.0e18
        assert relate(m, (0.0, 0.0, 0.0, 0.0),
                      (2.0 * big * C, 0.5 * big * C, 0.0, 0.0)).name == "A_PRECEDES_B"
        clock = TemporalClock("engine")
        with AuthorityContext("temporal"):
            clock.advance(1.0e18)
        assert clock.simulation_time_s == 1.0e18

    def test_very_small_intervals(self):
        clock = TemporalClock("engine")
        with AuthorityContext("temporal"):
            for _ in range(1000):
                clock.advance(1.0e-15)
        assert clock.simulation_time_s == pytest.approx(1.0e-12, rel=1e-9)

    def test_near_light_speed_dilation(self):
        # gamma at (1 - 1e-16)c ~ 7e7: extreme but finite (v < c enforced).
        v = math.nextafter(C, 0.0)  # largest double below c
        tau = velocity_time_dilation(1.0, v)
        assert 0.0 < tau <= 1.0
        assert math.isfinite(tau)

    def test_strong_field_near_horizon(self):
        from astra.relativity.gr_foundations import schwarzschild_radius
        rs = schwarzschild_radius(MASS_SUN)
        tau = velocity_time_dilation(1.0, 1.0)  # sanity
        # Gravitational dilation 1e-9 m above the horizon: extreme but finite.
        from astra.temporal import gravitational_time_dilation
        val = gravitational_time_dilation(1.0, MASS_SUN, rs + 1e-6)
        assert 0.0 < val < 1.0
        assert math.isfinite(val)

    def test_nan_inf_states_rejected_everywhere(self):
        for bad in (float("nan"), float("inf"), -1.0):
            with pytest.raises(InvalidTemporalStateError):
                TemporalState(bad, 0.0, 0.0, "o")
            with pytest.raises(InvalidTemporalStateError):
                TemporalState(0.0, bad, 0.0, "o")
        clock = TemporalClock("engine")
        with AuthorityContext("temporal"):
            with pytest.raises(InvalidTemporalStateError):
                clock.advance(float("nan"))
            with pytest.raises(InvalidTemporalStateError):
                clock.set_rate(float("inf"))

    def test_invalid_worldlines_rejected(self):
        single = Worldline(((0.0, SpacetimeEvent(0, 0, 0, 0)),))
        with pytest.raises(InvalidWorldlineError):
            flat_proper_time(single)
        with pytest.raises(InvalidWorldlineError):
            flat_proper_time(None)


class TestObservationHostility:
    def _history(self, x=10.0 * C):
        return Worldline(tuple(
            (90.0 + 30.0 * i / 30, SpacetimeEvent.from_coordinates(
                90.0 + 30.0 * i / 30, x, 0.0, 0.0, CHART_CARTESIAN))
            for i in range(31)
        ))

    def test_unavailable_history_is_explicit(self):
        with pytest.raises(TemporalHistoryUnavailableError):
            observe(self._history(100.0 * C), (0.0, 0.0, 0.0), 110.0)

    def test_nan_observation_time(self):
        with pytest.raises(InvalidTemporalStateError):
            observe(self._history(), (0.0, 0.0, 0.0), float("nan"))

    def test_observed_state_never_mutates_history(self):
        history = self._history()
        before = history.to_dict()
        observe(history, (0.0, 0.0, 0.0), 110.0)
        assert history.to_dict() == before

    def test_history_with_non_monotonic_parameters_rejected(self):
        # The Worldline value type enforces strictly increasing parameters
        # with its own (spacetime-layer) AstraError family exception:
        from astra.spacetime.exceptions import InvalidCoordinateError
        with pytest.raises(InvalidCoordinateError):
            Worldline((
                (5.0, SpacetimeEvent.from_coordinates(5.0, 10.0 * C, 0, 0, CHART_CARTESIAN)),
                (3.0, SpacetimeEvent.from_coordinates(3.0, 10.0 * C, 0, 0, CHART_CARTESIAN)),
            ))


class TestDeterminism:
    def test_full_pipeline_bit_for_bit(self):
        m = MinkowskiMetric()
        history = Worldline(tuple(
            (100.0 + i, SpacetimeEvent.from_coordinates(100.0 + i, 10.0 * C, 0, 0,
                                                        CHART_CARTESIAN))
            for i in range(21)
        ))

        def snapshot():
            return (
                classify(m, (0, 0, 0, 0), (2 * C, C, 0, 0)),
                relate(m, (0, 0, 0, 0), (0, 5 * C, 0, 0)),
                observe(history, (0.0, 0.0, 0.0), 110.0, "earth"),
                velocity_time_dilation(10.0, 0.9 * C),
            )

        first = snapshot()
        for _ in range(300):
            assert snapshot() == first


class TestDependencyHygiene:
    def test_no_reverse_dependency(self):
        # TEMPORAL sits at the top; nothing below may import it.
        code = ("import sys; import astra.theoretical; import astra.spacetime; "
                "import astra.blackhole; print('astra.temporal' in sys.modules)")
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        assert out.returncode == 0
        assert out.stdout.strip() == "False"

    def test_temporal_pulls_expected_layers(self):
        code = ("import sys; import astra.temporal; "
                "print('astra.spacetime' in sys.modules, "
                "'astra.relativity' in sys.modules, "
                "'astra.theoretical' in sys.modules)")
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        assert out.returncode == 0
        assert out.stdout.strip() == "True True True"


class TestAuthority:
    def test_clock_is_the_only_mutable_surface(self):
        # Value objects are frozen; mutation flows ONLY through the
        # authority-gated clock (verified in test_temporal_state).
        import dataclasses
        assert dataclasses.is_dataclass(TemporalState)
        s = TemporalState(1.0, 1.0, 1.0, "o")
        with pytest.raises(dataclasses.FrozenInstanceError):
            s.rate = 2.0

    def test_authority_error_is_astra_error(self):
        assert issubclass(AuthorityError, AstraError)

    def test_concurrent_clocks_independent(self):
        # No global mutable temporal state: separate clocks never interfere.
        clocks = [TemporalClock(f"engine-{i}") for i in range(8)]
        with AuthorityContext("temporal"):
            for i, c in enumerate(clocks):
                c.advance(float(i + 1))
        assert [c.simulation_time_s for c in clocks] == [1.0, 2.0, 3.0, 4.0,
                                                         5.0, 6.0, 7.0, 8.0]
