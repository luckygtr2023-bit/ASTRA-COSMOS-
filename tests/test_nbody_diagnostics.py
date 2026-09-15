import math
import pytest
from astra.mathematics import Vector3
from astra.nbody import (
    NBodyBody, total_linear_momentum, kinetic_energy,
    total_energy, total_angular_momentum,
    center_of_mass, center_of_mass_velocity,
    to_barycentric, from_barycentric,
)


def _body(id_, m, p, v):
    return NBodyBody(id=id_, mass=m,
                     position=Vector3(*p), velocity=Vector3(*v))


class TestLinearMomentum:
    def test_zero(self):
        bodies = [
            _body("a", 1.0, (0, 0, 0), (0, 0, 0)),
            _body("b", 2.0, (1, 0, 0), (0, 0, 0)),
        ]
        assert total_linear_momentum(bodies) == Vector3(0, 0, 0)

    def test_nonzero(self):
        bodies = [
            _body("a", 2.0, (0, 0, 0), (1, 0, 0)),
            _body("b", 3.0, (0, 0, 0), (0, 1, 0)),
        ]
        P = total_linear_momentum(bodies)
        assert P == Vector3(2, 3, 0)


class TestKineticEnergy:
    def test_one_body(self):
        bodies = [_body("a", 2.0, (0, 0, 0), (3, 4, 0))]
        assert kinetic_energy(bodies) == pytest.approx(25.0)


class TestAngularMomentum:
    def test_about_origin(self):
        bodies = [_body("a", 1.0, (1, 0, 0), (0, 1, 0))]
        L = total_angular_momentum(bodies, about_origin=True)
        assert L.z == pytest.approx(1.0)

    def test_about_com(self):
        bodies = [
            _body("a", 1.0, (1, 0, 0), (0, 1, 0)),
            _body("b", 1.0, (-1, 0, 0), (0, -1, 0)),
        ]
        # About origin: sum of r x mv = 1 + 1 = 2 in z.
        L_o = total_angular_momentum(bodies, about_origin=True)
        assert L_o.z == pytest.approx(2.0)
        # About COM (origin): COM is origin, so same.
        L_cm = total_angular_momentum(bodies, about_origin=False)
        assert L_cm.z == pytest.approx(2.0)


class TestCOM:
    def test_equal_masses(self):
        bodies = [
            _body("a", 1.0, (0, 0, 0), (0, 0, 0)),
            _body("b", 1.0, (2, 0, 0), (0, 0, 0)),
        ]
        assert center_of_mass(bodies) == Vector3(1, 0, 0)

    def test_velocity(self):
        bodies = [
            _body("a", 1.0, (0, 0, 0), (1, 0, 0)),
            _body("b", 1.0, (0, 0, 0), (3, 0, 0)),
        ]
        assert center_of_mass_velocity(bodies) == Vector3(2, 0, 0)

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            center_of_mass([])


class TestBarycentricTransform:
    def test_round_trip(self):
        bodies = [
            _body("a", 1.0, (1, 0, 0), (0, 1, 0)),
            _body("b", 2.0, (3, 0, 0), (0, -1, 0)),
        ]
        R = center_of_mass(bodies)
        V = center_of_mass_velocity(bodies)
        bary = to_barycentric(bodies)
        restored = from_barycentric(bary, R, V)
        for orig, r in zip(bodies, restored):
            assert orig.position.distance_to(r.position) < 1e-15
            assert orig.velocity.distance_to(r.velocity) < 1e-15
