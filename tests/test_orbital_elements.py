import math
import pytest
from astra.mathematics import Vector3
from astra.orbital import (
    OrbitalState, ClassicalOrbitalElements,
    state_to_elements, elements_to_state,
    ConicType, classify_conic,
    is_elliptic, is_parabolic, is_hyperbolic,
    specific_orbital_energy, specific_angular_momentum,
    DegenerateOrbitError, InvalidOrbitError,
)


MU_EARTH = 3.986004418e14  # m^3/s^2


def _circular_state(r: float, mu: float) -> OrbitalState:
    v = math.sqrt(mu / r)
    return OrbitalState(position=Vector3(r, 0, 0),
                        velocity=Vector3(0, v, 0),
                        mu=mu)


class TestCircular:
    def test_elements(self):
        s = _circular_state(7.0e6, MU_EARTH)
        el = state_to_elements(s)
        assert el.eccentricity == pytest.approx(0.0, abs=1e-12)
        assert el.is_circular
        assert el.semi_latus_rectum == pytest.approx(7.0e6, rel=1e-9)

    def test_roundtrip(self):
        s = _circular_state(7.0e6, MU_EARTH)
        el = state_to_elements(s)
        s2 = elements_to_state(el, epoch=s.epoch)
        assert s2.position.distance_to(s.position) < 1e-6
        assert s2.velocity.distance_to(s.velocity) < 1e-6


class TestElliptic:
    def test_molniya_like(self):
        # r_peri = 6.6e6, r_apo = 4.6e7
        r_p, r_a = 6.6e6, 4.6e7
        a = 0.5 * (r_p + r_a)
        e = (r_a - r_p) / (r_a + r_p)
        p = a * (1 - e ** 2)
        v_p = math.sqrt(MU_EARTH * (2.0 / r_p - 1.0 / a))
        s = OrbitalState(position=Vector3(r_p, 0, 0),
                         velocity=Vector3(0, v_p, 0),
                         mu=MU_EARTH)
        el = state_to_elements(s)
        assert el.eccentricity == pytest.approx(e, abs=1e-12)
        assert el.semi_latus_rectum == pytest.approx(p, rel=1e-9)
        assert el.semi_major_axis == pytest.approx(a, rel=1e-9)
        assert el.periapsis == pytest.approx(r_p, rel=1e-9)
        assert el.apoapsis == pytest.approx(r_a, rel=1e-9)

    def test_roundtrip(self):
        r_p, r_a = 1.0e7, 3.5e7
        a = 0.5 * (r_p + r_a)
        v_p = math.sqrt(MU_EARTH * (2.0 / r_p - 1.0 / a))
        s = OrbitalState(position=Vector3(r_p, 0, 0),
                         velocity=Vector3(0, v_p, 0),
                         mu=MU_EARTH)
        el = state_to_elements(s)
        s2 = elements_to_state(el)
        assert s2.position.distance_to(s.position) / r_p < 1e-9
        assert s2.velocity.distance_to(s.velocity) / v_p < 1e-9

    def test_inclined_roundtrip(self):
        s = OrbitalState(
            position=Vector3(1.0e7, 0.0, 0.0),
            velocity=Vector3(0.0, 5000.0, 3000.0),
            mu=MU_EARTH,
        )
        el = state_to_elements(s)
        s2 = elements_to_state(el)
        assert s2.position.distance_to(s.position) / 1.0e7 < 1e-9
        assert s2.velocity.distance_to(s.velocity) / 6000.0 < 1e-9


class TestHyperbolic:
    def test_escape_like(self):
        r = 7.0e6
        v_esc = math.sqrt(2.0 * MU_EARTH / r)
        s = OrbitalState(
            position=Vector3(r, 0, 0),
            velocity=Vector3(0, v_esc * 1.2, 0),
            mu=MU_EARTH,
        )
        el = state_to_elements(s)
        assert el.eccentricity > 1.0
        assert classify_conic(el.eccentricity) is ConicType.HYPERBOLIC
        assert el.semi_major_axis < 0.0

    def test_roundtrip(self):
        r = 7.0e6
        v = math.sqrt(2.0 * MU_EARTH / r) * 1.5
        s = OrbitalState(
            position=Vector3(r, 0, 0),
            velocity=Vector3(0, v, 0),
            mu=MU_EARTH,
        )
        el = state_to_elements(s)
        s2 = elements_to_state(el)
        assert s2.position.distance_to(s.position) / r < 1e-9
        assert s2.velocity.distance_to(s.velocity) / v < 1e-9


class TestParabolic:
    def test_exact_parabolic(self):
        r = 7.0e6
        v_esc = math.sqrt(2.0 * MU_EARTH / r)
        s = OrbitalState(
            position=Vector3(r, 0, 0),
            velocity=Vector3(0, v_esc, 0),
            mu=MU_EARTH,
        )
        el = state_to_elements(s)
        assert abs(el.eccentricity - 1.0) < 1e-8
        assert classify_conic(el.eccentricity) is ConicType.PARABOLIC


class TestDegenerate:
    def test_zero_position(self):
        with pytest.raises(DegenerateOrbitError):
            state_to_elements(OrbitalState(
                position=Vector3(0, 0, 0),
                velocity=Vector3(1, 0, 0),
                mu=MU_EARTH,
            ))

    def test_radial_trajectory(self):
        with pytest.raises(DegenerateOrbitError):
            state_to_elements(OrbitalState(
                position=Vector3(1e6, 0, 0),
                velocity=Vector3(100, 0, 0),
                mu=MU_EARTH,
            ))


class TestEnergy:
    def test_elliptic_energy_negative(self):
        s = _circular_state(7.0e6, MU_EARTH)
        assert specific_orbital_energy(s) < 0.0

    def test_parabolic_energy_zero(self):
        r = 7.0e6
        v = math.sqrt(2.0 * MU_EARTH / r)
        s = OrbitalState(position=Vector3(r, 0, 0),
                         velocity=Vector3(0, v, 0),
                         mu=MU_EARTH)
        assert abs(specific_orbital_energy(s)) < 1e-6

    def test_angular_momentum(self):
        s = _circular_state(7.0e6, MU_EARTH)
        h = specific_angular_momentum(s)
        assert h.z > 0.0
