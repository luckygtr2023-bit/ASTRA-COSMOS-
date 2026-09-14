import math
import pytest
from astra.spacecraft import SpacecraftMass, SpacecraftInvalidMassError


class TestConstruction:
    def test_valid(self):
        m = SpacecraftMass(dry_mass=100.0, propellant_mass=900.0)
        assert m.total_mass == 1000.0
        assert m.inverse_mass == pytest.approx(0.001)

    def test_zero_dry(self):
        m = SpacecraftMass(dry_mass=0.0, propellant_mass=1.0)
        assert m.total_mass == 1.0

    def test_zero_propellant(self):
        m = SpacecraftMass(dry_mass=1.0, propellant_mass=0.0)
        assert m.total_mass == 1.0
        assert m.is_empty

    def test_negative_dry(self):
        with pytest.raises(SpacecraftInvalidMassError):
            SpacecraftMass(dry_mass=-1.0, propellant_mass=1.0)

    def test_negative_prop(self):
        with pytest.raises(SpacecraftInvalidMassError):
            SpacecraftMass(dry_mass=1.0, propellant_mass=-1.0)

    def test_nan(self):
        with pytest.raises(SpacecraftInvalidMassError):
            SpacecraftMass(dry_mass=float("nan"), propellant_mass=1.0)

    def test_inf(self):
        with pytest.raises(SpacecraftInvalidMassError):
            SpacecraftMass(dry_mass=float("inf"), propellant_mass=1.0)

    def test_both_zero(self):
        with pytest.raises(SpacecraftInvalidMassError):
            SpacecraftMass(dry_mass=0.0, propellant_mass=0.0)


class TestConsumption:
    def test_consume_less_than_available(self):
        m = SpacecraftMass(dry_mass=1.0, propellant_mass=10.0)
        removed = m.consume(3.0)
        assert removed == 3.0
        assert m.propellant_mass == 7.0

    def test_consume_more_than_available(self):
        m = SpacecraftMass(dry_mass=1.0, propellant_mass=10.0)
        removed = m.consume(999.0)
        assert removed == 10.0
        assert m.propellant_mass == 0.0
        assert m.is_empty

    def test_consume_never_negative(self):
        m = SpacecraftMass(dry_mass=1.0, propellant_mass=0.0)
        assert m.consume(1.0) == 0.0
        assert m.propellant_mass == 0.0

    def test_consume_zero(self):
        m = SpacecraftMass(dry_mass=1.0, propellant_mass=10.0)
        assert m.consume(0.0) == 0.0
        assert m.propellant_mass == 10.0

    def test_consume_negative_rejected(self):
        m = SpacecraftMass(dry_mass=1.0, propellant_mass=10.0)
        with pytest.raises(SpacecraftInvalidMassError):
            m.consume(-1.0)

    def test_consume_nan_rejected(self):
        m = SpacecraftMass(dry_mass=1.0, propellant_mass=10.0)
        with pytest.raises(SpacecraftInvalidMassError):
            m.consume(float("nan"))


class TestSerialization:
    def test_round_trip(self):
        m = SpacecraftMass(dry_mass=100.0, propellant_mass=900.0)
        d = m.to_dict()
        m2 = SpacecraftMass.from_dict(d)
        assert m2.dry_mass == 100.0
        assert m2.propellant_mass == 900.0

    def test_missing_fields(self):
        with pytest.raises(SpacecraftInvalidMassError):
            SpacecraftMass.from_dict({"dry_mass": 1.0})
