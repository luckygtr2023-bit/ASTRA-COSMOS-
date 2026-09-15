"""Adversarial Celestial tests: domain objects, blackhole delegation,
hygiene, no-embedded-data guarantees, dependency direction, determinism."""
import math
import os
import subprocess
import sys

import pytest

from astra.core.exceptions import AstraError
from astra.celestial import (
    AGN,
    BlackHoleObject,
    Nebula,
    CelestialError,
    CyclicHierarchyError,
    DataProvenance,
    DuplicateNodeError,
    Exoplanet,
    Galaxy,
    HierarchyNode,
    IncompletePhysicalDataError,
    InvalidPropertyError,
    NeutronStar,
    ObjectCategory,
    Pulsar,
    Quasar,
    SpectralType,
    Star,
    create_black_hole_object,
    create_identity,
    create_planet,
    create_properties,
    create_star,
)
from astra.celestial.objects import CelestialObject


def _sun_props():
    return create_properties(DataProvenance.REAL_DATA, mass_kg=1.989e30,
                             radius_m=6.957e8, temperature_k=5772.0)


class TestErrorHierarchy:
    def test_all_celestial_errors_are_astra_errors(self):
        for exc in (CelestialError, InvalidPropertyError,
                    IncompletePhysicalDataError, CyclicHierarchyError,
                    DuplicateNodeError):
            assert issubclass(exc, AstraError)

    def test_validation_errors_are_value_errors(self):
        assert issubclass(InvalidPropertyError, ValueError)
        assert issubclass(DuplicateNodeError, ValueError)


class TestDomainObjects:
    def test_star_taxonomy(self):
        star = create_star(create_identity("Sun"), _sun_props(),
                           spectral_type=SpectralType.G)
        assert star.category is ObjectCategory.STAR
        assert star.spectral_type is SpectralType.G
        assert star.get_mass_kg() == pytest.approx(1.989e30)
        assert star.get_radius_m() == pytest.approx(6.957e8)

    def test_planet_family_factory(self):
        for kind, cls in ((ObjectCategory.PLANET, "Planet"),
                          (ObjectCategory.DWARF_PLANET, "DwarfPlanet"),
                          (ObjectCategory.MOON, "Moon"),
                          (ObjectCategory.EXOPLANET, "Exoplanet")):
            obj = create_planet(create_identity(kind.value),
                                create_properties(DataProvenance.REAL_DATA,
                                                  mass_kg=1.0e24), kind)
            assert type(obj).__name__ == cls
            assert obj.category is kind
        with pytest.raises(TypeError):
            create_planet(create_identity("X"),
                          create_properties(DataProvenance.SIMULATED_DATA),
                          ObjectCategory.GALAXY)

    def test_incomplete_star_blocked_from_pipelines(self):
        star = create_star(create_identity("NoMassStar"),
                           create_properties(DataProvenance.SIMULATED_DATA))
        with pytest.raises(IncompletePhysicalDataError):
            star.get_mass_kg()

    def test_deep_space_objects_constructible(self):
        for cls in (Nebula, Galaxy, Quasar, AGN):
            obj = cls(create_identity(cls.__name__),
                      create_properties(DataProvenance.REAL_DATA, mass_kg=1.0e36),
                      ObjectCategory[cls.__name__.upper()])
            assert obj.category.value == cls.__name__.upper()

    def test_pulsar_period_domain(self):
        props = create_properties(DataProvenance.REAL_DATA, mass_kg=1.4e30)
        assert Pulsar(create_identity("Crab"), props,
                      ObjectCategory.PULSAR, pulse_period_s=0.033).pulse_period_s == (
            pytest.approx(0.033))
        for bad in (0.0, -1.0, float("nan"), float("inf")):
            with pytest.raises(InvalidPropertyError):
                Pulsar(create_identity("Bad"), props, ObjectCategory.PULSAR,
                       pulse_period_s=bad)

    def test_neutron_star_magnetic_field_domain(self):
        props = create_properties(DataProvenance.REAL_DATA, mass_kg=1.4e30)
        assert NeutronStar(create_identity("NS"), props,
                           ObjectCategory.NEUTRON_STAR,
                           magnetic_field_tesla=1.0e8).magnetic_field_tesla == 1.0e8
        with pytest.raises(InvalidPropertyError):
            NeutronStar(create_identity("NS"), props, ObjectCategory.NEUTRON_STAR,
                        magnetic_field_tesla=-1.0)


class TestBlackHoleDelegation:
    def test_geometry_delegates_to_blackhole_layer(self):
        from astra.blackhole.schwarzschild import (
            photon_sphere_radius,
            schwarzschild_radius,
        )
        bh = create_black_hole_object(create_identity("SgrA*"),
                                      create_properties(DataProvenance.REAL_DATA,
                                                        mass_kg=8.26e36),
                                      spin_param=0.5)
        assert bh.schwarzschild_radius_m() == schwarzschild_radius(8.26e36)
        assert bh.photon_sphere_radius_m() == photon_sphere_radius(8.26e36)
        state = bh.get_black_hole_state()
        assert state.mass_kg == pytest.approx(8.26e36)
        assert state.spin_param == 0.5

    def test_spin_validation_delegated(self):
        from astra.blackhole import InvalidSpinParameterError
        with pytest.raises(InvalidSpinParameterError):
            create_black_hole_object(
                create_identity("Naked"),
                create_properties(DataProvenance.THEORETICAL_MODEL,
                                  mass_kg=1.0e30),
                spin_param=1.5)

    def test_unknown_mass_delegates_to_incomplete_error(self):
        # require_mass_kg (celestial) fires BEFORE blackhole validation.
        with pytest.raises(IncompletePhysicalDataError):
            create_black_hole_object(
                create_identity("NoMassBH"),
                create_properties(DataProvenance.THEORETICAL_MODEL))


class TestNoEmbeddedData:
    def test_no_dataset_files_in_module(self):
        import astra.celestial as pkg
        base = os.path.dirname(pkg.__file__)
        for fname in os.listdir(base):
            assert not fname.endswith((".csv", ".json", ".parquet", ".fits",
                                       ".h5", ".db")), fname

    def test_no_catalog_data_blobs(self):
        # No hardcoded Gaia/JPL/SIMBAD designations: source contains only
        # the architecture, not embedded astronomy.
        import astra.celestial as pkg
        base = os.path.dirname(pkg.__file__)
        for fname in sorted(os.listdir(base)):
            if fname.endswith(".py"):
                with open(os.path.join(base, fname)) as fh:
                    src = fh.read()
                assert "l, b, parallax" not in src  # no rows of data
                assert not any(
                    line.strip().startswith(("[", "{\"")) for line in src.splitlines()
                )


class TestDependencyHygiene:
    def test_no_reverse_dependency(self):
        code = ("import sys; import astra.temporal; import astra.theoretical; "
                "print('astra.celestial' in sys.modules)")
        out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                             text=True)
        assert out.returncode == 0
        assert out.stdout.strip() == "False"

    def test_blackhole_delegation_is_lazy(self):
        # Merely importing the architecture does NOT load the blackhole
        # engine; delegation happens at BlackHoleObject CONSTRUCTION.
        code = (
            "import sys; import astra.celestial; "
            "before = 'astra.blackhole' in sys.modules; "
            "from astra.celestial import create_black_hole_object, "
            "create_identity, create_properties, DataProvenance; "
            "create_black_hole_object(create_identity('BH'), "
            "create_properties(DataProvenance.THEORETICAL_MODEL, "
            "mass_kg=1e30)); "
            "print(before, 'astra.blackhole' in sys.modules)"
        )
        out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                             text=True)
        assert out.returncode == 0
        assert out.stdout.strip() == "False True"


class TestDeterminism:
    def test_definition_pipeline_bit_for_bit(self):
        def snapshot():
            star = create_star(create_identity("Sun"), _sun_props(),
                               spectral_type=SpectralType.G)
            bh = create_black_hole_object(
                create_identity("SgrA*"),
                create_properties(DataProvenance.REAL_DATA, mass_kg=8.26e36),
                spin_param=0.9)
            root = HierarchyNode(create_identity("Root"))
            return (star.object_id if hasattr(star, "object_id") else None,
                    star.identity.object_id,
                    star.get_mass_kg(),
                    bh.schwarzschild_radius_m(),
                    bh.get_black_hole_state().model,
                    root.identity.object_id)

        first = snapshot()
        for _ in range(500):
            assert snapshot() == first

    def test_frozen_definitions_reject_mutation(self):
        import dataclasses
        star = create_star(create_identity("Sun"), _sun_props())
        with pytest.raises(dataclasses.FrozenInstanceError):
            star.category = ObjectCategory.BLACK_HOLE
        assert isinstance(star, CelestialObject)
