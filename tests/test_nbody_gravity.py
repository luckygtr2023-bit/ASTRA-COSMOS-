import math
import pytest
from astra.mathematics import Vector3
from astra.physics import GRAVITATIONAL_CONSTANT
from astra.nbody import (
    NBodyBody, pairwise_acceleration, pairwise_potential,
    compute_accelerations, gravitational_potential_energy,
    NBodySingularityError,
)


class TestPairwiseAcceleration:
    def test_direction(self):
        a_i, a_j = pairwise_acceleration(
            Vector3(0, 0, 0), Vector3(1, 0, 0), 1.0, 1.0, softening=0.0
        )
        # Body i is pulled toward j (+x); body j is pulled toward i (-x)
        assert a_i.x > 0.0
        assert a_j.x < 0.0
        assert a_i.y == 0.0 and a_i.z == 0.0

    def test_magnitude_inverse_square(self):
        a1, _ = pairwise_acceleration(
            Vector3(0, 0, 0), Vector3(1, 0, 0), 1.0, 1.0, softening=0.0
        )
        a2, _ = pairwise_acceleration(
            Vector3(0, 0, 0), Vector3(2, 0, 0), 1.0, 1.0, softening=0.0
        )
        assert a1.magnitude() / a2.magnitude() == pytest.approx(4.0)

    def test_mass_scaling(self):
        a1, _ = pairwise_acceleration(
            Vector3(0, 0, 0), Vector3(1, 0, 0), 1.0, 1.0, softening=0.0
        )
        a2, _ = pairwise_acceleration(
            Vector3(0, 0, 0), Vector3(1, 0, 0), 1.0, 3.0, softening=0.0
        )
        assert a2.x == pytest.approx(3.0 * a1.x)

    def test_antisymmetric(self):
        a_i, a_j = pairwise_acceleration(
            Vector3(0, 0, 0), Vector3(1, 2, 3), 2.0, 5.0, softening=1e-6
        )
        # momentum conservation for the pair: m_i a_i + m_j a_j = 0
        total = a_i * 2.0 + a_j * 5.0
        assert total.magnitude() < 1e-30

    def test_softening_prevents_singularity(self):
        a_i, a_j = pairwise_acceleration(
            Vector3(0, 0, 0), Vector3(0, 0, 0), 1.0, 1.0, softening=1e-3
        )
        assert math.isfinite(a_i.magnitude())
        assert a_i.magnitude() == 0.0  # zero displacement -> zero direction

    def test_zero_softening_singularity(self):
        with pytest.raises(NBodySingularityError):
            pairwise_acceleration(
                Vector3(0, 0, 0), Vector3(0, 0, 0), 1.0, 1.0, softening=0.0
            )


class TestComputeAccelerations:
    def test_two_bodies(self):
        b1 = NBodyBody(id="a", mass=1.0,
                       position=Vector3(0, 0, 0), velocity=Vector3(0, 0, 0))
        b2 = NBodyBody(id="b", mass=1.0,
                       position=Vector3(1, 0, 0), velocity=Vector3(0, 0, 0))
        acc = compute_accelerations([b1, b2], softening=0.0)
        assert acc[0].x > 0.0
        assert acc[1].x < 0.0

    def test_three_bodies_net(self):
        # Symmetric three-body: acceleration on the center body is zero.
        b1 = NBodyBody(id="a", mass=1.0,
                       position=Vector3(-1, 0, 0), velocity=Vector3(0, 0, 0))
        b2 = NBodyBody(id="b", mass=1.0,
                       position=Vector3(0, 0, 0), velocity=Vector3(0, 0, 0))
        b3 = NBodyBody(id="c", mass=1.0,
                       position=Vector3(1, 0, 0), velocity=Vector3(0, 0, 0))
        acc = compute_accelerations([b1, b2, b3], softening=0.0)
        assert acc[1].magnitude() == pytest.approx(0.0, abs=1e-30)

    def test_zero_bodies(self):
        assert compute_accelerations([], softening=0.0) == []

    def test_one_body(self):
        b = NBodyBody(id="a", mass=1.0,
                      position=Vector3(0, 0, 0), velocity=Vector3(0, 0, 0))
        acc = compute_accelerations([b], softening=0.0)
        assert len(acc) == 1
        assert acc[0] == Vector3(0, 0, 0)

    def test_deterministic(self):
        bodies = [
            NBodyBody(id="a", mass=1.0,
                      position=Vector3(0.1, 0.2, 0.3), velocity=Vector3(0, 0, 0)),
            NBodyBody(id="b", mass=2.0,
                      position=Vector3(1.0, -0.5, 0.4), velocity=Vector3(0, 0, 0)),
            NBodyBody(id="c", mass=3.0,
                      position=Vector3(-0.7, 1.2, -0.2), velocity=Vector3(0, 0, 0)),
        ]
        a1 = compute_accelerations(bodies)
        a2 = compute_accelerations(bodies)
        for x, y in zip(a1, a2):
            assert x == y


class TestPotentialEnergy:
    def test_two_bodies(self):
        b1 = NBodyBody(id="a", mass=1.0,
                       position=Vector3(0, 0, 0), velocity=Vector3(0, 0, 0))
        b2 = NBodyBody(id="b", mass=1.0,
                       position=Vector3(1, 0, 0), velocity=Vector3(0, 0, 0))
        U = gravitational_potential_energy([b1, b2], softening=0.0)
        assert U == pytest.approx(-GRAVITATIONAL_CONSTANT)

    def test_pair_counted_once(self):
        # 3 bodies -> 3 pairs
        b1 = NBodyBody(id="a", mass=1.0,
                       position=Vector3(0, 0, 0), velocity=Vector3(0, 0, 0))
        b2 = NBodyBody(id="b", mass=1.0,
                       position=Vector3(1, 0, 0), velocity=Vector3(0, 0, 0))
        b3 = NBodyBody(id="c", mass=1.0,
                       position=Vector3(0, 1, 0), velocity=Vector3(0, 0, 0))
        U = gravitational_potential_energy([b1, b2, b3], softening=0.0)
        expected = -GRAVITATIONAL_CONSTANT * (1.0 + 1.0 + 1.0 / math.sqrt(2.0))
        assert U == pytest.approx(expected)
