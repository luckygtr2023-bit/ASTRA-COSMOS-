"""Spacetime events, worldlines, and coordinate chart tests."""
import dataclasses
import math

import pytest

from astra.relativity.core import SPEED_OF_LIGHT as C
from astra.relativity.four_vectors import FourVector
from astra.spacetime import (
    CHART_CARTESIAN,
    CHART_SPHERICAL,
    InvalidCoordinateError,
    SpacetimeEvent,
    Worldline,
    cartesian_to_spherical,
    create_event,
    spherical_to_cartesian,
)


class TestSpacetimeEvent:
    def test_from_coordinates_multiplies_by_c(self):
        ev = create_event(2.0, 1.0, -2.0, 3.0)
        assert ev.ct_m == pytest.approx(2.0 * C)
        assert ev.time_sec == pytest.approx(2.0)
        assert (ev.x, ev.y, ev.z) == (1.0, -2.0, 3.0)

    def test_immutable(self):
        ev = create_event(0.0, 1.0, 2.0, 3.0)
        with pytest.raises(dataclasses.FrozenInstanceError):
            ev.x = 99.0

    def test_nan_inf_rejected(self):
        with pytest.raises(InvalidCoordinateError):
            create_event(float("nan"), 0.0, 0.0, 0.0)
        with pytest.raises(InvalidCoordinateError):
            create_event(0.0, float("inf"), 0.0, 0.0)

    def test_non_numeric_rejected(self):
        with pytest.raises(InvalidCoordinateError):
            create_event("t", 0.0, 0.0, 0.0)

    def test_four_vector_interop(self):
        ev = create_event(1.5, 4.0, -5.0, 6.0)
        fv = ev.to_four_vector()
        assert isinstance(fv, FourVector)
        assert (fv.t, fv.x, fv.y, fv.z) == (ev.ct_m, ev.x, ev.y, ev.z)
        ev2 = SpacetimeEvent.from_four_vector(fv)
        assert ev2 == ev

    def test_persistence_round_trip(self):
        ev = create_event(3.25, 100.0, -0.5, 8.0, CHART_SPHERICAL)
        restored = SpacetimeEvent.from_dict(ev.to_dict())
        assert restored == ev

    def test_unknown_chart_rejected(self):
        with pytest.raises(InvalidCoordinateError):
            SpacetimeEvent(0.0, 0.0, 0.0, 0.0, "hyperbolic")


class TestChartConversions:
    def test_round_trip(self):
        r, theta, phi = cartesian_to_spherical(3.0, 4.0, 12.0)
        x, y, z = spherical_to_cartesian(r, theta, phi)
        assert x == pytest.approx(3.0, rel=1e-12)
        assert y == pytest.approx(4.0, rel=1e-12)
        assert z == pytest.approx(12.0, rel=1e-12)

    def test_known_values(self):
        r, theta, phi = cartesian_to_spherical(1.0, 1.0, math.sqrt(2.0))
        assert r == pytest.approx(2.0)
        assert theta == pytest.approx(math.pi / 4)
        assert phi == pytest.approx(math.pi / 4)

    def test_origin_rejected(self):
        with pytest.raises(InvalidCoordinateError):
            cartesian_to_spherical(0.0, 0.0, 0.0)

    def test_negative_radius_rejected(self):
        with pytest.raises(InvalidCoordinateError):
            spherical_to_cartesian(-1.0, 0.5, 0.5)


class TestWorldline:
    def _samples(self):
        return (
            (0.0, create_event(0.0, 0.0, 0.0, 0.0)),
            (0.5, create_event(0.5, 1.0, 0.0, 0.0)),
            (1.0, create_event(1.0, 2.0, 0.0, 0.0)),
        )

    def test_ordered_construction(self):
        w = Worldline(self._samples())
        assert w.parameters == (0.0, 0.5, 1.0)
        assert len(w.events) == 3
        assert w.final_event().x == pytest.approx(2.0)

    def test_unordered_rejected(self):
        bad = (
            (0.0, create_event(0.0, 0.0, 0.0, 0.0)),
            (0.5, create_event(0.5, 1.0, 0.0, 0.0)),
            (0.4, create_event(1.0, 2.0, 0.0, 0.0)),
        )
        with pytest.raises(InvalidCoordinateError):
            Worldline(bad)

    def test_empty_final_event_rejected(self):
        with pytest.raises(InvalidCoordinateError):
            Worldline(()).final_event()

    def test_persistence_round_trip(self):
        w = Worldline(self._samples())
        restored = Worldline.from_dict(w.to_dict())
        assert restored.parameters == w.parameters
        assert restored.events == w.events

    def test_immutable(self):
        w = Worldline(self._samples())
        with pytest.raises(dataclasses.FrozenInstanceError):
            w.samples = ()
