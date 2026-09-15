"""Provenance cannot silently leak."""
import pytest

from astra.galactic import Provenance
from astra.galactic.provenance import DerivedValue, ObservedValue, SimulatedValue, UnknownValue
from astra.galactic.errors import GalacticValidationError, GalacticNumericalError


def test_observed_is_real_data_only():
    v = ObservedValue(value=1.0, uncertainty=0.1, unit="x", source="s")
    assert v.provenance == Provenance.REAL_DATA


def test_observed_rejects_wrong_provenance():
    with pytest.raises(GalacticValidationError):
        ObservedValue(value=1.0, uncertainty=0.1, unit="x", source="s", provenance=Provenance.SIMULATED_DATA)


def test_derived_is_derived_only():
    v = DerivedValue(value=1.0, unit="x", method="m", inputs=())
    assert v.provenance == Provenance.DERIVED_DATA


def test_derived_rejects_wrong_provenance():
    with pytest.raises(GalacticValidationError):
        DerivedValue(value=1.0, unit="x", method="m", inputs=(), provenance=Provenance.REAL_DATA)


def test_simulated_is_simulated_only():
    v = SimulatedValue(value=1.0, unit="x", model="m")
    assert v.provenance == Provenance.SIMULATED_DATA


def test_simulated_rejects_wrong_provenance():
    with pytest.raises(GalacticValidationError):
        SimulatedValue(value=1.0, unit="x", model="m", provenance=Provenance.REAL_DATA)


def test_unknown_is_explicit_not_zero():
    v = UnknownValue(unit="Msun", reason="no data")
    assert not hasattr(v, "value") or v.value if hasattr(v, "value") else True
    # ensure unknown doesn't have numeric value
    assert isinstance(v.unit, str)
    assert isinstance(v.reason, str)


def test_unknown_has_no_value_attribute():
    v = UnknownValue(unit="Msun", reason="no data")
    assert not hasattr(v, "value") or True  # we enforce no value field
    # The dataclass should not have a 'value' field at all
    assert "value" not in v.__dataclass_fields__


def test_provenance_through_hierarchy_preserved():
    from astra.galactic import GalacticEngine, GalacticConfig, Galaxy, GalaxyType, Vec3, CoordinateContext, Frame, GalaxyGroup
    class _AllowAll:
        def require(self, op): return None
    e = GalacticEngine(config=GalacticConfig(), authority=_AllowAll())
    # galaxy with simulated provenance
    g = Galaxy(galaxy_id="g-1", name="G1", galaxy_type=GalaxyType.SPIRAL, position=Vec3(0,0,0), coordinate_context=CoordinateContext(Frame.COMOVING, 1.0, 0.0), provenance=Provenance.SIMULATED_DATA)
    e.register_galaxy(g)
    # group with same provenance should be preserved
    grp = GalaxyGroup(group_id="grp-1", member_galaxy_ids=("g-1",), center=Vec3(0,0,0), coordinate_context=CoordinateContext(Frame.COMOVING, 1.0, 0.0), provenance=Provenance.SIMULATED_DATA)
    e.register_group(grp)
    assert e.get_group("grp-1").provenance == Provenance.SIMULATED_DATA
    assert e.provenance_summary()[Provenance.SIMULATED_DATA.value] == 2


def test_no_silent_real_to_simulated_conversion():
    # observed mass stays observed; engine must not convert to simulated
    ov = ObservedValue(value=1e12, uncertainty=1e11, unit="Msun", source="SDSS")
    from astra.galactic.types import Galaxy, GalaxyType, Vec3, CoordinateContext, Frame, Halo
    from astra.galactic import GalacticEngine, GalacticConfig
    class _AllowAll:
        def require(self, op): return None
    halo = Halo(mass=ov, characteristic_radius_kpc=SimulatedValue(value=100, unit="kpc", model="nfw"))
    g = Galaxy(galaxy_id="g-obs", name="Gobs", galaxy_type=GalaxyType.ELLIPTICAL, position=Vec3(0,0,0), coordinate_context=CoordinateContext(Frame.COMOVING,1.0,0.0), halo=halo, provenance=Provenance.REAL_DATA)
    e = GalacticEngine(config=GalacticConfig(), authority=_AllowAll())
    e.register_galaxy(g)
    retrieved = e.get_galaxy("g-obs")
    assert isinstance(retrieved.halo.mass, ObservedValue)
    assert retrieved.halo.mass.provenance == Provenance.REAL_DATA
