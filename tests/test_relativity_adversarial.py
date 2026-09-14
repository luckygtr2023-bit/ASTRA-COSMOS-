"""Adversarial Relativity tests: NaN/Inf, v >= c, singular metrics, boosts."""
import math

import pytest

from astra.mathematics import Vector3
from astra.relativity.core import (
    SPEED_OF_LIGHT,
    beta,
    kinetic_energy,
    lorentz_factor,
    relativistic_mass,
    total_energy,
)
from astra.relativity.exceptions import (
    DegenerateMetricError,
    InvalidRestMassError,
    InvalidVelocityError,
    LightSpeedViolation,
    RelativityError,
)
from astra.relativity.four_vectors import FourVector
from astra.relativity.gr_foundations import (
    schwarzschild_radius,
    weak_field_time_dilation,
)
from astra.relativity.lorentz import boost_x, inverse_boost_x


class TestVelocityValidation:
    def test_adversarial_velocity(self):
        # NaN / Inf speeds are caller bugs: rejected as ValueError (and as
        # RelativityError, so the ASTRA error family also catches them).
        with pytest.raises(ValueError):
            lorentz_factor(float("nan"))

        with pytest.raises(ValueError):
            lorentz_factor(float("inf"))

        with pytest.raises(InvalidVelocityError):
            lorentz_factor(Vector3(float("nan"), 0.0, 0.0))

    def test_error_family_membership(self):
        assert issubclass(InvalidVelocityError, RelativityError)
        assert issubclass(InvalidVelocityError, ValueError)

    def test_beta_rejects_non_finite(self):
        with pytest.raises(InvalidVelocityError):
            beta(float("nan"))
        with pytest.raises(InvalidVelocityError):
            beta(float("-inf"))

    def test_absolute_zero_velocity(self):
        assert lorentz_factor(0.0) == 1.0

    def test_extremely_low_speed_stability(self):
        # v = 0.01 m/s: beta^2 ~ 1.1e-21 is far below float epsilon, so the
        # Lorentz factor rounds to exactly 1.0 - and kinetic energy MUST
        # still return the classical 1/2 m v^2 = 5e-5 J, not 0. This is the
        # regression for the catastrophic-cancellation bug in (gamma - 1).
        assert lorentz_factor(0.01) == 1.0
        ke = kinetic_energy(1.0, 0.01)
        assert ke == pytest.approx(0.5 * 1.0 * 0.01 ** 2, rel=1e-9)

    def test_near_c_extreme_gamma(self):
        near_c = 299792457.99999
        gamma = lorentz_factor(near_c)
        assert gamma > 1000.0

    def test_massive_object_cannot_reach_c(self):
        for v in (SPEED_OF_LIGHT, SPEED_OF_LIGHT * 1.0000001, float("2e9")):
            with pytest.raises(LightSpeedViolation):
                lorentz_factor(v)

    def test_energy_at_v_c_raises_not_infinite(self):
        with pytest.raises(LightSpeedViolation):
            total_energy(1.0, SPEED_OF_LIGHT)
        with pytest.raises(LightSpeedViolation):
            kinetic_energy(1.0, SPEED_OF_LIGHT * 1.5)


class TestMassValidation:
    def test_negative_rest_mass_rejected(self):
        with pytest.raises(InvalidRestMassError):
            relativistic_mass(-1.0, 0.0)

    def test_non_finite_rest_mass_rejected(self):
        with pytest.raises(InvalidRestMassError):
            relativistic_mass(float("nan"), 0.0)
        with pytest.raises(InvalidRestMassError):
            relativistic_mass(float("inf"), 10.0)

    def test_zero_rest_mass_allowed(self):
        # Massless-limit bookkeeping stays finite for v < c.
        assert relativistic_mass(0.0, 100.0) == 0.0
        assert total_energy(0.0, 100.0) == 0.0


class TestBoostAdversarial:
    def test_boost_at_c_rejected(self):
        v = FourVector(1.0, 0.0, 0.0, 0.0)
        with pytest.raises(LightSpeedViolation):
            boost_x(v, SPEED_OF_LIGHT)
        with pytest.raises(LightSpeedViolation):
            boost_x(v, -SPEED_OF_LIGHT * 1.01)

    def test_boost_nan_rejected(self):
        v = FourVector(1.0, 0.0, 0.0, 0.0)
        with pytest.raises(InvalidVelocityError):
            boost_x(v, float("nan"))

    def test_round_trip_is_identity(self):
        v = SPEED_OF_LIGHT * 0.95
        event = FourVector(123.5, -77.25, 8.0, -3.5)
        restored = inverse_boost_x(boost_x(event, v), v)
        assert math.isclose(event.t, restored.t, rel_tol=1e-9, abs_tol=1e-9)
        assert math.isclose(event.x, restored.x, rel_tol=1e-9, abs_tol=1e-9)


class TestMetricAdversarial:
    def test_negative_mass_rejected(self):
        with pytest.raises(DegenerateMetricError):
            schwarzschild_radius(-1.0)

    def test_non_finite_mass_rejected(self):
        with pytest.raises(DegenerateMetricError):
            schwarzschild_radius(float("nan"))

    def test_zero_or_negative_radius_rejected(self):
        with pytest.raises(DegenerateMetricError):
            weak_field_time_dilation(1.0e20, 0.0)
        with pytest.raises(DegenerateMetricError):
            weak_field_time_dilation(1.0e20, -5.0)


class TestDeterminism:
    def test_pure_functions_repeat_identically(self):
        # ASTRA determinism policy: identical inputs -> identical outputs.
        for _ in range(3):
            assert lorentz_factor(12345.0) == lorentz_factor(12345.0)
            assert kinetic_energy(7.0, 250.0) == kinetic_energy(7.0, 250.0)
            assert schwarzschild_radius(2.0e30) == schwarzschild_radius(2.0e30)
            assert weak_field_time_dilation(2.0e30, 1.0e12) == weak_field_time_dilation(
                2.0e30, 1.0e12
            )
