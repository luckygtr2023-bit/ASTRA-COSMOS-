"""Celestial property tests: unknown-data semantics, validation, provenance."""
import dataclasses

import pytest

from astra.celestial import (
    DataProvenance,
    IncompletePhysicalDataError,
    InvalidPropertyError,
    ProvenanceTag,
    ScientificConfidence,
    create_properties,
)
from astra.celestial.properties import CelestialProperties


class TestUnknownDataSemantics:
    def test_unknown_is_none_not_zero(self):
        p = create_properties(DataProvenance.SIMULATED_DATA)
        assert p.mass_kg is None
        assert p.radius_m is None
        assert p.temperature_k is None

    def test_zero_is_a_value_not_a_placeholder(self):
        # 0.0 K mass/temperature are physical impossibilities for stars and
        # are rejected - unknown data must be None, never 0.0.
        with pytest.raises(InvalidPropertyError):
            create_properties(DataProvenance.REAL_DATA, mass_kg=0.0)
        with pytest.raises(InvalidPropertyError):
            create_properties(DataProvenance.REAL_DATA, temperature_k=0.0)

    def test_accessors_fail_explicitly_on_unknown(self):
        p = create_properties(DataProvenance.SIMULATED_DATA)
        with pytest.raises(IncompletePhysicalDataError):
            p.require_mass_kg()
        with pytest.raises(IncompletePhysicalDataError):
            p.require_radius_m()

    def test_accessors_return_values_when_known(self):
        p = create_properties(DataProvenance.REAL_DATA, mass_kg=2.0, radius_m=3.0)
        assert p.require_mass_kg() == 2.0
        assert p.require_radius_m() == 3.0
        assert p.is_complete_for_dynamics

    def test_incomplete_error_names_the_missing_field(self):
        with pytest.raises(IncompletePhysicalDataError, match="mass_kg"):
            create_properties(DataProvenance.SIMULATED_DATA).require_mass_kg()


class TestDomainValidation:
    @pytest.mark.parametrize("field", ["mass_kg", "radius_m", "temperature_k",
                                       "luminosity_w"])
    def test_negative_rejected(self, field):
        with pytest.raises(InvalidPropertyError):
            create_properties(DataProvenance.REAL_DATA, **{field: -1e-9})

    @pytest.mark.parametrize("field", ["mass_kg", "radius_m", "temperature_k"])
    def test_nan_inf_rejected(self, field):
        for bad in (float("nan"), float("inf")):
            with pytest.raises(InvalidPropertyError):
                create_properties(DataProvenance.REAL_DATA, **{field: bad})

    def test_non_numeric_rejected(self):
        with pytest.raises(InvalidPropertyError):
            create_properties(DataProvenance.REAL_DATA, mass_kg="heavy")
        with pytest.raises(InvalidPropertyError):
            create_properties(DataProvenance.REAL_DATA, mass_kg=True)

    def test_valid_boundary_zero_for_peculiar_fields(self):
        # absolute magnitude/metallicity can legitimately be <= 0.
        p = create_properties(DataProvenance.REAL_DATA, absolute_magnitude=4.83)
        assert p.absolute_magnitude == pytest.approx(4.83)


class TestProvenance:
    def test_all_provenance_classes_exist(self):
        for name in ("REAL_DATA", "DERIVED_DATA", "SIMULATED_DATA",
                     "THEORETICAL_MODEL", "SPECULATIVE_MODEL"):
            assert DataProvenance[name].value == name

    def test_default_confidence_mapping(self):
        assert (ProvenanceTag(DataProvenance.REAL_DATA).confidence
                is ScientificConfidence.OBSERVATIONAL)
        assert (ProvenanceTag(DataProvenance.SPECULATIVE_MODEL).confidence
                is ScientificConfidence.MODEL_DEPENDENT)

    def test_tag_requires_real_provenance(self):
        with pytest.raises(TypeError):
            ProvenanceTag("REAL_DATA")
        with pytest.raises(ValueError):
            ProvenanceTag(DataProvenance.REAL_DATA, "")

    def test_properties_carry_tag(self):
        p = create_properties(DataProvenance.DERIVED_DATA, source_label="mass-lum",
                              mass_kg=1.0e20)
        assert p.provenance.provenance is DataProvenance.DERIVED_DATA
        assert p.provenance.source_label == "mass-lum"


class TestImmutabilityAndUpdates:
    def test_frozen(self):
        p = create_properties(DataProvenance.REAL_DATA, mass_kg=1.0)
        with pytest.raises(dataclasses.FrozenInstanceError):
            p.mass_kg = 2.0

    def test_with_updates_returns_new_block(self):
        original = create_properties(DataProvenance.SIMULATED_DATA)
        updated = original.with_updates(
            mass_kg=1.0e20,
            provenance=ProvenanceTag(DataProvenance.DERIVED_DATA, "mass-lum"),
        )
        assert original.mass_kg is None
        assert updated.mass_kg == 1.0e20
        assert updated.provenance.provenance is DataProvenance.DERIVED_DATA

    def test_updates_are_revalidated(self):
        p = create_properties(DataProvenance.REAL_DATA, mass_kg=1.0)
        with pytest.raises(InvalidPropertyError):
            p.with_updates(mass_kg=-5.0)

    def test_persistence_round_trip_including_unknowns(self):
        p = create_properties(DataProvenance.REAL_DATA, mass_kg=1.5e20,
                              temperature_k=300.0)
        restored = CelestialProperties.from_dict(p.to_dict())
        assert restored == p
        assert restored.radius_m is None  # unknown survives the round trip

    def test_persistence_rejects_corrupt_provenance(self):
        payload = create_properties(DataProvenance.REAL_DATA, mass_kg=1.0).to_dict()
        payload["provenance"]["provenance"] = "MADE_UP"
        with pytest.raises(ValueError):
            CelestialProperties.from_dict(payload)
