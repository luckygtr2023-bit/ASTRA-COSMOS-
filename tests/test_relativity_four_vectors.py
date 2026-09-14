"""Four-vector tests: interval classification, invariance, proper time."""
import math

import pytest

from astra.relativity.core import SPEED_OF_LIGHT
from astra.relativity.exceptions import RelativityError, SpacelikeIntervalError
from astra.relativity.four_vectors import (
    FourVector,
    SpacetimeEvent,
    SpacetimeIntervalType,
)
from astra.relativity.lorentz import boost_x, inverse_boost_x


class TestIntervalClassification:
    def test_timelike(self):
        # Timelike: t > x (in ct units).
        v_time = FourVector(5.0, 1.0, 0.0, 0.0)
        assert v_time.interval_type() == SpacetimeIntervalType.TIMELIKE

    def test_spacelike(self):
        # Spacelike: x > t.
        v_space = FourVector(1.0, 5.0, 0.0, 0.0)
        assert v_space.interval_type() == SpacetimeIntervalType.SPACELIKE

    def test_null(self):
        # Null: t == x.
        v_null = FourVector(3.0, 3.0, 0.0, 0.0)
        assert v_null.interval_type() == SpacetimeIntervalType.NULL

    def test_null_with_transverse_separation(self):
        # t^2 == x^2 + y^2 exactly: lightlike.
        v = FourVector(5.0, 3.0, 4.0, 0.0)
        assert v.interval_type() == SpacetimeIntervalType.NULL

    def test_invariant_sq_signature(self):
        # Signature (-1, 1, 1, 1): -(t^2) + x^2 + y^2 + z^2.
        assert FourVector(1.0, 2.0, 3.0, 4.0).invariant_sq() == pytest.approx(
            -1.0 + 4.0 + 9.0 + 16.0
        )


class TestLorentzInvariance:
    def test_boost_preserves_invariant(self):
        v = SPEED_OF_LIGHT * 0.5
        event = FourVector(10.0, 5.0, 0.0, 0.0)
        invariant_before = event.invariant_sq()

        boosted = boost_x(event, v)
        invariant_after = boosted.invariant_sq()

        assert math.isclose(invariant_before, invariant_after, rel_tol=1e-9)

    def test_boost_preserves_invariant_transverse(self):
        # y and z components must pass through untouched and still cancel.
        v = SPEED_OF_LIGHT * 0.9
        event = FourVector(100.0, 25.0, 10.0, -5.0)
        boosted = boost_x(event, v)
        assert math.isclose(event.invariant_sq(), boosted.invariant_sq(), rel_tol=1e-9)
        assert boosted.y == event.y
        assert boosted.z == event.z

    def test_inverse_transform(self):
        v = SPEED_OF_LIGHT * 0.9
        event = FourVector(100.0, 25.0, 10.0, -5.0)

        boosted = boost_x(event, v)
        restored = inverse_boost_x(boosted, v)

        assert math.isclose(event.t, restored.t, rel_tol=1e-9)
        assert math.isclose(event.x, restored.x, rel_tol=1e-9)
        assert math.isclose(event.y, restored.y, rel_tol=1e-9)
        assert math.isclose(event.z, restored.z, rel_tol=1e-9)

    def test_lightlike_vector_stays_lightlike_under_boost(self):
        # A photon's displacement (t = x) maps to (t' = x') in any x-frame.
        photon = FourVector(10.0, 10.0, 0.0, 0.0)
        boosted = boost_x(photon, SPEED_OF_LIGHT * 0.7)
        assert boosted.interval_type() == SpacetimeIntervalType.NULL


class TestSpacetimeEvent:
    def test_from_coordinates_multiplies_by_c(self):
        event = SpacetimeEvent.from_coordinates(2.0, 1.0, 0.0, -4.0)
        assert event.t == pytest.approx(2.0 * SPEED_OF_LIGHT)
        assert (event.x, event.y, event.z) == (1.0, 0.0, -4.0)

    def test_proper_time_stationary_events(self):
        # Two events on the same rest-worldline: dtau == coordinate dt.
        a = SpacetimeEvent.from_coordinates(0.0, 0.0, 0.0, 0.0)
        b = SpacetimeEvent.from_coordinates(7.0, 0.0, 0.0, 0.0)
        assert a.proper_time_to(b) == pytest.approx(7.0, rel=1e-12)

    def test_proper_time_moving_clock_is_shorter(self):
        # A clock moving 3 m during 1 s of coordinate time ticks slightly less.
        a = SpacetimeEvent.from_coordinates(0.0, 0.0, 0.0, 0.0)
        b = SpacetimeEvent.from_coordinates(1.0, 3.0, 0.0, 0.0)
        tau = a.proper_time_to(b)
        assert 0.0 < tau < 1.0
        assert math.isclose(tau, math.sqrt(1.0 - 9.0 / SPEED_OF_LIGHT ** 2), rel_tol=1e-12)

    def test_proper_time_null_interval_is_zero(self):
        a = SpacetimeEvent.from_coordinates(0.0, 0.0, 0.0, 0.0)
        b = SpacetimeEvent.from_coordinates(1.0, SPEED_OF_LIGHT, 0.0, 0.0)
        assert a.proper_time_to(b) == 0.0

    def test_proper_time_spacelike_raises(self):
        a = SpacetimeEvent.from_coordinates(0.0, 0.0, 0.0, 0.0)
        b = SpacetimeEvent.from_coordinates(0.0, 100.0, 0.0, 0.0)
        with pytest.raises(SpacelikeIntervalError):
            a.proper_time_to(b)
        # And it integrates with the ASTRA error family.
        assert isinstance(SpacelikeIntervalError("x"), RelativityError)


class TestValueType:
    def test_equality_and_repr(self):
        a = FourVector(1.0, 2.0, 3.0, 4.0)
        b = FourVector(1.0, 2.0, 3.0, 4.0)
        assert a == b
        assert a != FourVector(1.0, 2.0, 3.0, 4.5)
        assert "FourVector" in repr(a)
        assert "SpacetimeEvent" in repr(SpacetimeEvent(0.0, 0.0, 0.0, 0.0))

    def test_components_persistence_tuple(self):
        # Serializable plain primitives (astra.core.persistence contract).
        c = FourVector(1.0, -2.0, 3.0, 0.5).components()
        assert c == (1.0, -2.0, 3.0, 0.5)
