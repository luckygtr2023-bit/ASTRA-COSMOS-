import math
import pytest
from astra.mathematics import Vector3
from astra.nbody import NBodyBody, NBodyInvalidMassError, InvalidBodyError


class TestNBodyBody:
    def test_valid(self):
        b = NBodyBody(id="earth", mass=5.97e24,
                      position=Vector3(1.0, 0.0, 0.0),
                      velocity=Vector3(0.0, 1.0, 0.0))
        assert b.id == "earth"
        assert b.mass == 5.97e24

    def test_empty_id(self):
        with pytest.raises(InvalidBodyError):
            NBodyBody(id="", mass=1.0,
                      position=Vector3(0, 0, 0), velocity=Vector3(0, 0, 0))

    def test_zero_mass(self):
        with pytest.raises(NBodyInvalidMassError):
            NBodyBody(id="x", mass=0.0,
                      position=Vector3(0, 0, 0), velocity=Vector3(0, 0, 0))

    def test_negative_mass(self):
        with pytest.raises(NBodyInvalidMassError):
            NBodyBody(id="x", mass=-1.0,
                      position=Vector3(0, 0, 0), velocity=Vector3(0, 0, 0))

    def test_nan_mass(self):
        with pytest.raises(NBodyInvalidMassError):
            NBodyBody(id="x", mass=float("nan"),
                      position=Vector3(0, 0, 0), velocity=Vector3(0, 0, 0))

    def test_inf_mass(self):
        with pytest.raises(NBodyInvalidMassError):
            NBodyBody(id="x", mass=float("inf"),
                      position=Vector3(0, 0, 0), velocity=Vector3(0, 0, 0))

    def test_nan_position(self):
        with pytest.raises(InvalidBodyError):
            NBodyBody(id="x", mass=1.0,
                      position=Vector3(float("nan"), 0, 0),
                      velocity=Vector3(0, 0, 0))

    def test_copy(self):
        b = NBodyBody(id="x", mass=1.0,
                      position=Vector3(1, 0, 0), velocity=Vector3(0, 1, 0))
        c = b.copy(mass=2.0)
        assert c.mass == 2.0
        assert c.position == b.position


class TestSerialization:
    def test_round_trip(self):
        b = NBodyBody(id="sun", mass=1.989e30,
                      position=Vector3(1.0, 2.0, 3.0),
                      velocity=Vector3(0.1, 0.2, 0.3))
        d = b.to_dict()
        b2 = NBodyBody.from_dict(d)
        assert b2 == b

    def test_missing_field(self):
        with pytest.raises(InvalidBodyError):
            NBodyBody.from_dict({"id": "x", "mass": 1.0})
