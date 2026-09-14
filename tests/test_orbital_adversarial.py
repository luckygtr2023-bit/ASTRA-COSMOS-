"""Adversarial orbital tests."""
import math
import pytest
from astra.mathematics import Vector3
from astra.orbital import (
    OrbitalState, state_to_elements, elements_to_state, propagate,
    specific_orbital_energy, classify_conic, ConicType,
    circular_velocity, escape_velocity, vis_viva,
    hohmann_transfer, plane_change_delta_v,
    solve_kepler_elliptic, solve_kepler_hyperbolic,
    DegenerateOrbitError, InvalidOrbitError, InvalidTransferError,
    KeplerConvergenceError,
)


MU_EARTH = 3.986004418e14


class TestNaNInf:
    def test_nan_position_rejected(self):
        with pytest.raises(InvalidOrbitError):
            OrbitalState(position=Vector3(float("nan"), 0, 0),
                         velocity=Vector3(1, 0, 0), mu=MU_EARTH)

    def test_inf_mu_rejected(self):
        with pytest.raises(InvalidOrbitError):
            OrbitalState(position=Vector3(1, 0, 0),
                         velocity=Vector3(1, 0, 0), mu=float("inf"))

    def test_negative_mu_rejected(self):
        with pytest.raises(InvalidOrbitError):
            OrbitalState(position=Vector3(1, 0, 0),
                         velocity=Vector3(1, 0, 0), mu=-MU_EARTH)

    def test_zero_mu_rejected(self):
        with pytest.raises(InvalidOrbitError):
            OrbitalState(position=Vector3(1, 0, 0),
                         velocity=Vector3(1, 0, 0), mu=0.0)


class TestExtremeScales:
    def test_small_orbit(self):
        r = 1.0e3
        v = math.sqrt(MU_EARTH / r)
        s = OrbitalState(position=Vector3(r, 0, 0),
                         velocity=Vector3(0, v, 0), mu=MU_EARTH)
        el = state_to_elements(s)
        assert el.eccentricity < 1e-8

    def test_large_orbit(self):
        r = 1.0e15
        v = math.sqrt(MU_EARTH / r)
        s = OrbitalState(position=Vector3(r, 0, 0),
                         velocity=Vector3(0, v, 0), mu=MU_EARTH)
        el = state_to_elements(s)
        assert el.eccentricity < 1e-8

    def test_high_eccentricity_near_parabolic(self):
        # e = 0.9999
        r_p = 1.0e7
        e = 0.9999
        p = r_p * (1.0 + e)
        a = p / (1.0 - e * e)
        v_p = math.sqrt(MU_EARTH * (2.0 / r_p - 1.0 / a))
        s = OrbitalState(position=Vector3(r_p, 0, 0),
                         velocity=Vector3(0, v_p, 0), mu=MU_EARTH)
        el = state_to_elements(s)
        assert abs(el.eccentricity - e) < 1e-6

    def test_long_propagation_energy_drift_bounded(self):
        r_p = 7.0e6
        r_a = 4.0e7
        a = 0.5 * (r_p + r_a)
        v_p = math.sqrt(MU_EARTH * (2.0 / r_p - 1.0 / a))
        s = OrbitalState(position=Vector3(r_p, 0, 0),
                         velocity=Vector3(0, v_p, 0), mu=MU_EARTH)
        eps0 = specific_orbital_energy(s)
        for _ in range(1000):
            s = propagate(s, 60.0)
        eps = specific_orbital_energy(s)
        assert abs(eps - eps0) / abs(eps0) < 1e-9


class TestClassifDegenerate:
    def test_zero_e(self):
        assert classify_conic(0.0) is ConicType.ELLIPTIC

    def test_one_e(self):
        assert classify_conic(1.0) is ConicType.PARABOLIC

    def test_above_one(self):
        assert classify_conic(1.5) is ConicType.HYPERBOLIC

    def test_negative_e(self):
        with pytest.raises(ValueError):
            classify_conic(-0.1)


class TestVisVivaErrors:
    def test_zero_r(self):
        with pytest.raises(InvalidOrbitError):
            vis_viva(0.0, 1.0e7, MU_EARTH)

    def test_zero_a(self):
        with pytest.raises(InvalidOrbitError):
            vis_viva(1.0e7, 0.0, MU_EARTH)


class TestTransferErrors:
    def test_negative_radius(self):
        with pytest.raises(InvalidTransferError):
            hohmann_transfer(-1.0e7, 4.0e7, MU_EARTH)

    def test_zero_mu(self):
        with pytest.raises(InvalidTransferError):
            hohmann_transfer(7.0e6, 4.0e7, 0.0)


class TestDeterminismMany:
    def test_repeated_conversions(self):
        s = OrbitalState(position=Vector3(7.0e6, 1.0e6, 2.0e6),
                         velocity=Vector3(-1000.0, 7000.0, 500.0),
                         mu=MU_EARTH)
        el = state_to_elements(s)
        for _ in range(100):
            s2 = elements_to_state(el)
            el2 = state_to_elements(s2)
            assert el2.eccentricity == pytest.approx(el.eccentricity, abs=1e-12)

    def test_repeated_propagation(self):
        s = OrbitalState(position=Vector3(7.0e6, 0, 0),
                         velocity=Vector3(0, 7500.0, 0),
                         mu=MU_EARTH)
        r1 = propagate(s, 1234.567).position.to_tuple()
        r2 = propagate(s, 1234.567).position.to_tuple()
        assert r1 == r2


class TestKeplerFailure:
    def test_invalid_e_elliptic(self):
        with pytest.raises(InvalidOrbitError):
            solve_kepler_elliptic(0.5, 1.5)

    def test_invalid_e_hyperbolic(self):
        with pytest.raises(InvalidOrbitError):
            solve_kepler_hyperbolic(0.5, 0.5)


class TestAngularMomentumDegenerate:
    def test_pure_radial(self):
        with pytest.raises(DegenerateOrbitError):
            state_to_elements(OrbitalState(
                position=Vector3(1e6, 0, 0),
                velocity=Vector3(1e3, 0, 0),
                mu=MU_EARTH,
            ))
