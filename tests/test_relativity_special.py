"""Special Relativity core tests: gamma, energies, momentum, c-limit."""
import math

import pytest

from astra.mathematics import Vector3
from astra.physics import kinetic_energy as classical_kinetic_energy
from astra.physics import linear_momentum
from astra.relativity.core import (
    SPEED_OF_LIGHT,
    beta,
    kinetic_energy,
    kinetic_energy_v,
    lorentz_factor,
    relativistic_mass,
    relativistic_momentum,
    total_energy,
    total_energy_v,
)
from astra.relativity.exceptions import LightSpeedViolation


class TestLorentzFactor:
    def test_low_speed(self):
        # v = 10 m/s (classical domain): gamma must be 1 to double precision.
        gamma = lorentz_factor(10.0)
        assert math.isclose(gamma, 1.0, rel_tol=1e-9)

    def test_high_speed(self):
        # v = 0.8c -> gamma = 5/3.
        gamma = lorentz_factor(SPEED_OF_LIGHT * 0.8)
        assert math.isclose(gamma, 1.6666666667, rel_tol=1e-7)

    def test_light_speed_violation(self):
        with pytest.raises(LightSpeedViolation):
            lorentz_factor(SPEED_OF_LIGHT)

        with pytest.raises(LightSpeedViolation):
            lorentz_factor(SPEED_OF_LIGHT * 1.1)

    def test_beta(self):
        assert beta(SPEED_OF_LIGHT * 0.5) == pytest.approx(0.5)
        assert beta(0.0) == 0.0

    def test_accepts_vector3_input(self):
        # Interop contract: classical Vector3 velocities are accepted.
        v = Vector3(3.0e7, 4.0e7, 0.0)  # |v| = 5e7 m/s
        assert lorentz_factor(v) == lorentz_factor(5.0e7)

    def test_determinism(self):
        values = [lorentz_factor(SPEED_OF_LIGHT * 0.37) for _ in range(5)]
        assert all(v == values[0] for v in values)


class TestMassAndEnergy:
    def test_relativistic_mass_at_rest(self):
        assert relativistic_mass(2.0, 0.0) == 2.0

    def test_relativistic_mass(self):
        m = relativistic_mass(1000.0, SPEED_OF_LIGHT * 0.8)
        assert math.isclose(m, 1000.0 * 5.0 / 3.0, rel_tol=1e-9)

    def test_total_energy_at_rest_is_rest_energy(self):
        m0 = 2.5
        assert total_energy(m0, 0.0) == pytest.approx(m0 * SPEED_OF_LIGHT ** 2)

    def test_kinetic_energy_classical_limit(self):
        m = 1000.0  # kg
        v = 10.0    # m/s
        rel_ke = kinetic_energy(m, v)
        classical_ke = 0.5 * m * v ** 2
        assert math.isclose(rel_ke, classical_ke, rel_tol=1e-5)

    def test_kinetic_energy_classical_convergence_sweep(self):
        # Converge to astra.physics 1/2 m |v|^2 across four decades of speed.
        m = 1.0
        for v in (1.0, 10.0, 1000.0, 1.0e5):
            ke_rel = kinetic_energy_v(m, Vector3(v, 0.0, 0.0))
            ke_cls = classical_kinetic_energy(m, Vector3(v, 0.0, 0.0))
            assert math.isclose(ke_rel, ke_cls, rel_tol=1e-6)

    def test_kinetic_energy_relativistic_regime(self):
        # At 0.8c: Ek = (gamma - 1) m c^2 = (2/3) m c^2.
        m = 1.0
        ek = kinetic_energy(m, SPEED_OF_LIGHT * 0.8)
        assert math.isclose(ek, (2.0 / 3.0) * SPEED_OF_LIGHT ** 2, rel_tol=1e-9)

    def test_total_energy_equals_rest_plus_kinetic(self):
        m0, v = 3.0, SPEED_OF_LIGHT * 0.6
        assert total_energy(m0, v) == pytest.approx(
            m0 * SPEED_OF_LIGHT ** 2 + kinetic_energy(m0, v), rel=1e-12
        )

    def test_total_energy_vector3_variant(self):
        v = Vector3(0.0, 0.0, SPEED_OF_LIGHT * 0.6)
        assert total_energy_v(3.0, v) == pytest.approx(total_energy(3.0, 0.6 * SPEED_OF_LIGHT))


class TestRelativisticMomentum:
    def test_converges_to_classical_momentum(self):
        # Interop contract: p = gamma m v -> m v as v -> 0.
        m = 5.0
        v = Vector3(10.0, -3.0, 7.0)
        p = relativistic_momentum(m, v)
        p_cls = linear_momentum(m, v)
        assert p.x == pytest.approx(p_cls.x, rel=1e-12)
        assert p.y == pytest.approx(p_cls.y, rel=1e-12)
        assert p.z == pytest.approx(p_cls.z, rel=1e-12)

    def test_scales_by_gamma(self):
        m = 2.0
        v = Vector3(SPEED_OF_LIGHT * 0.6, 0.0, 0.0)  # gamma = 1.25
        p = relativistic_momentum(m, v)
        assert p == Vector3(m * 1.25 * v.x, 0.0, 0.0)
