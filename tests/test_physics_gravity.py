import math
import pytest
from astra.mathematics import Vector3
from astra.physics import (
    GravitySource, mutual_gravity_force,
    GRAVITATIONAL_CONSTANT, InvalidGravityError,
)


class TestMutualGravity:
    def test_attraction_direction(self):
        # Body 1 at origin, body 2 at (1, 0, 0). Force on 1 points toward 2.
        f = mutual_gravity_force(1.0, Vector3(0, 0, 0),
                                 1.0, Vector3(1, 0, 0),
                                 eps=0.0)
        assert f.x > 0
        assert f.y == 0 and f.z == 0

    def test_magnitude_1_over_r2(self):
        f1 = mutual_gravity_force(1.0, Vector3(0, 0, 0),
                                  1.0, Vector3(1, 0, 0), eps=0.0)
        f2 = mutual_gravity_force(1.0, Vector3(0, 0, 0),
                                  1.0, Vector3(2, 0, 0), eps=0.0)
        assert f1.magnitude() / f2.magnitude() == pytest.approx(4.0)

    def test_newtons_third_law(self):
        f12 = mutual_gravity_force(3.0, Vector3(0, 0, 0),
                                   5.0, Vector3(2, 1, 0), eps=1e-6)
        f21 = mutual_gravity_force(5.0, Vector3(2, 1, 0),
                                   3.0, Vector3(0, 0, 0), eps=1e-6)
        # f21 == -f12 (bit-near identical)
        assert f21.x == pytest.approx(-f12.x, abs=1e-30)
        assert f21.y == pytest.approx(-f12.y, abs=1e-30)
        assert f21.z == pytest.approx(-f12.z, abs=1e-30)

    def test_softening_finite_at_zero(self):
        f = mutual_gravity_force(1.0, Vector3(0, 0, 0),
                                 1.0, Vector3(0, 0, 0), eps=1e-3)
        assert math.isfinite(f.magnitude())

    def test_no_softening_at_zero_raises(self):
        with pytest.raises(InvalidGravityError):
            mutual_gravity_force(1.0, Vector3(0, 0, 0),
                                 1.0, Vector3(0, 0, 0), eps=0.0)


class TestGravitySource:
    def test_single_source(self):
        src = GravitySource(softening=0.0)
        src.add_body(5.0, Vector3(1.0, 0.0, 0.0))
        f = src.force_on(2.0, Vector3(0, 0, 0))
        expected_mag = GRAVITATIONAL_CONSTANT * 5.0 * 2.0 / (1.0 ** 2)
        assert f.magnitude() == pytest.approx(expected_mag)

    def test_multi_source_superposition(self):
        src = GravitySource(softening=0.0)
        src.add_body(1.0, Vector3(1.0, 0.0, 0.0))
        src.add_body(1.0, Vector3(-1.0, 0.0, 0.0))
        f = src.force_on(1.0, Vector3(0, 0, 0))
        # Two equal pulls from opposite directions cancel.
        assert f.magnitude() == pytest.approx(0.0, abs=1e-30)

    def test_clear(self):
        src = GravitySource()
        src.add_body(1.0, Vector3(0, 0, 0))
        src.clear()
        assert src.force_on(1.0, Vector3(1, 0, 0)) == Vector3(0, 0, 0)


class TestDeterminism:
    def test_repeated_eval_identical(self):
        src = GravitySource()
        src.add_body(5.0, Vector3(1, 2, 3))
        src.add_body(3.0, Vector3(-4, -5, -6))
        f1 = src.force_on(1.0, Vector3(0, 0, 0))
        f2 = src.force_on(1.0, Vector3(0, 0, 0))
        assert f1 == f2
