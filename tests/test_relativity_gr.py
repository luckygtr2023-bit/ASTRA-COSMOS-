"""General Relativity foundations tests: r_s and weak-field dilation."""
import math

import pytest

from astra.physics.constants import GRAVITATIONAL_CONSTANT
from astra.relativity.core import C_SQUARED, SPEED_OF_LIGHT
from astra.relativity.exceptions import DegenerateMetricError, RelativityError
from astra.relativity.gr_foundations import (
    G,
    schwarzschild_radius,
    weak_field_time_dilation,
)

MASS_EARTH = 5.972e24      # kg
R_EARTH_SURFACE = 6371000.0  # m


class TestSchwarzschildRadius:
    def test_earth(self):
        rs = schwarzschild_radius(MASS_EARTH)
        # Earth's r_s is ~8.87 mm.
        assert 0.008 < rs < 0.009

    def test_solar_mass(self):
        # Sun: r_s ~ 2.95 km.
        rs = schwarzschild_radius(1.989e30)
        assert 2953.0 < rs < 2955.0

    def test_zero_mass_is_flat(self):
        assert schwarzschild_radius(0.0) == 0.0

    def test_uses_physics_layer_gravitational_constant(self):
        # Contract: single source of truth for G (no duplication).
        m = 1.0e20
        assert schwarzschild_radius(m) == pytest.approx(
            2.0 * GRAVITATIONAL_CONSTANT * m / C_SQUARED, rel=1e-15
        )
        assert G == GRAVITATIONAL_CONSTANT


class TestWeakFieldDilation:
    def test_earth_surface(self):
        dilation = weak_field_time_dilation(MASS_EARTH, R_EARTH_SURFACE)
        assert dilation > 1.0
        assert dilation < 1.000000002  # very weak field

    def test_stronger_deeper_in_field(self):
        deep = weak_field_time_dilation(MASS_EARTH, R_EARTH_SURFACE / 2.0)
        surface = weak_field_time_dilation(MASS_EARTH, R_EARTH_SURFACE)
        assert deep > surface > 1.0

    def test_first_order_newtonian_limit(self):
        # For r >> r_s: dt/dtau ~ 1 + GM/(rc^2) (first order).
        m, r = 1.0e20, 1.0e9
        dilation = weak_field_time_dilation(m, r)
        first_order = 1.0 + GRAVITATIONAL_CONSTANT * m / (r * SPEED_OF_LIGHT ** 2)
        assert math.isclose(dilation, first_order, rel_tol=1e-12)

    def test_degenerate_metric(self):
        mass_bh = 2e30  # ~1 solar mass
        rs = schwarzschild_radius(mass_bh)
        with pytest.raises(DegenerateMetricError):
            weak_field_time_dilation(mass_bh, rs * 0.5)

    def test_at_horizon_raises(self):
        mass_bh = 2e30
        rs = schwarzschild_radius(mass_bh)
        with pytest.raises(DegenerateMetricError):
            weak_field_time_dilation(mass_bh, rs)

    def test_error_family(self):
        assert isinstance(DegenerateMetricError("x"), RelativityError)
