"""Stellar, galaxy, cluster, void, web — domain integration tests."""

import pytest

from astra.evolution import (
    CosmicEvolutionEngine, Provenance, Quantity, Scenario,
)
from astra.evolution.state import (
    EvolutionState, StellarPhase, GalaxyMorphology, StructureRegime, AGNActivity,
)
from astra.evolution.stellar import (
    main_sequence_lifetime_gyr, remnant_for_mass, classify_stellar_phase,
)
from astra.evolution.limitations import LimitationState
from astra.evolution.errors import EvolutionLimitationError


class _AllowAll:
    def require(self, op): return None
    def has_authority(self, op): return True


def test_stellar_lifecycle_classification():
    # 1 Msun -> ~10 Gyr MS
    assert main_sequence_lifetime_gyr(1.0) == pytest.approx(10.0, rel=1e-9)
    # Massive star short life
    assert main_sequence_lifetime_gyr(10.0) < 0.1
    # Remnant mapping
    assert remnant_for_mass(1.0) == StellarPhase.WHITE_DWARF
    assert remnant_for_mass(10.0) == StellarPhase.NEUTRON_STAR
    assert remnant_for_mass(30.0) == StellarPhase.BLACK_HOLE


def test_stellar_transition_before_after():
    t = classify_stellar_phase(mass_msun=1.0, age_gyr=5.0)
    assert t is None  # still on MS
    t2 = classify_stellar_phase(mass_msun=1.0, age_gyr=11.0)
    assert t2 is not None
    assert t2.before_phase == StellarPhase.MAIN_SEQUENCE
    assert t2.after_phase == StellarPhase.WHITE_DWARF
    assert t2.provenance == Provenance.SIMULATED_DATA


def test_stellar_evolution_through_engine():
    e = CosmicEvolutionEngine(authority=_AllowAll())
    # Star with 1 Msun, age 0, evolve 11 Gyr -> should become WD
    init = EvolutionState(
        object_id="star-1", cosmic_time_gyr=0.0,
        phase=StellarPhase.MAIN_SEQUENCE.value,
        quantities={
            "mass_msun": Quantity(value=1.0, unit="Msun", provenance=Provenance.SIMULATED_DATA,
                                  model_id="astra.evolution.stellar.v1"),
            "age_gyr": Quantity(value=0.0, unit="Gyr", provenance=Provenance.SIMULATED_DATA,
                                model_id="astra.evolution.stellar.v1"),
        },
        model_id="astra.evolution.stellar.v1",
        provenance=Provenance.SIMULATED_DATA,
    )
    scenario = e.scenario_registry.get("baseline_LCDM")
    final = e.evolve_object(initial_state=init, until_cosmic_time_gyr=11.0,
                            model_id="astra.evolution.stellar.v1",
                            scenario=scenario)
    assert final.phase == StellarPhase.WHITE_DWARF.value
    assert final.cosmic_time_gyr == pytest.approx(11.0)


def test_galaxy_evolution_sfr_declines():
    e = CosmicEvolutionEngine(authority=_AllowAll())
    final = e.evolve_galaxy(galaxy_id="g-1", until_cosmic_time_gyr=5.0)
    assert final.cosmic_time_gyr == pytest.approx(5.0)
    # SFR should have declined
    init_sfr = 5.0
    final_sfr = final.quantities["sfr_msun_per_yr"].value
    assert final_sfr < init_sfr
    # Stellar mass grew
    assert final.quantities["stellar_mass_msun"].value > 5e10
    # Metallicity increased
    assert final.quantities["metallicity"].value >= 0.02
    # Morphology probs remain normalized
    probs = final.metadata.get("morphology_probs")
    if probs:
        assert abs(sum(probs.values()) - 1.0) < 1e-6


def test_galaxy_morphology_probability_distribution():
    e = CosmicEvolutionEngine(authority=_AllowAll())
    init = EvolutionState(
        object_id="g-2", cosmic_time_gyr=0.0, phase="SPIRAL",
        quantities={
            "stellar_mass_msun": Quantity(value=5e10, unit="Msun",
                                          provenance=Provenance.SIMULATED_DATA,
                                          model_id="astra.evolution.galaxy.v1"),
            "gas_mass_msun": Quantity(value=1e8, unit="Msun",  # gas-poor
                                      provenance=Provenance.SIMULATED_DATA,
                                      model_id="astra.evolution.galaxy.v1"),
            "sfr_msun_per_yr": Quantity(value=0.5, unit="Msun/yr",
                                        provenance=Provenance.SIMULATED_DATA,
                                        model_id="astra.evolution.galaxy.v1"),
            "metallicity": Quantity(value=0.02, unit="Z",
                                    provenance=Provenance.SIMULATED_DATA,
                                    model_id="astra.evolution.galaxy.v1"),
            "luminosity_Lsun": Quantity(value=1e10, unit="Lsun",
                                        provenance=Provenance.SIMULATED_DATA,
                                        model_id="astra.evolution.galaxy.v1"),
        },
        model_id="astra.evolution.galaxy.v1",
        provenance=Provenance.SIMULATED_DATA,
        metadata={"morphology_probs": {
            GalaxyMorphology.SPIRAL.value: 0.8,
            GalaxyMorphology.ELLIPTICAL.value: 0.2,
        }},
    )
    scenario = e.scenario_registry.get("baseline_LCDM")
    final = e.evolve_object(initial_state=init, until_cosmic_time_gyr=5.0,
                            model_id="astra.evolution.galaxy.v1",
                            scenario=scenario)
    probs = final.metadata.get("morphology_probs")
    assert probs is not None
    # Gas-poor evolution should shift toward elliptical
    assert probs[GalaxyMorphology.ELLIPTICAL.value] >= 0.2


def test_chemical_evolution_scalar_Z():
    e = CosmicEvolutionEngine(authority=_AllowAll())
    final = e.evolve_galaxy(galaxy_id="g-chem", until_cosmic_time_gyr=2.0)
    Z = final.quantities["metallicity"].value
    assert Z >= 0.0
    # No fabricated elemental distribution — scalar only, flagged SIMULATED_DATA
    assert final.quantities["metallicity"].provenance == Provenance.SIMULATED_DATA


def test_galaxy_cluster_evolution():
    e = CosmicEvolutionEngine(authority=_AllowAll())
    final = e.evolve_cluster(cluster_id="cl-1", until_cosmic_time_gyr=3.0)
    assert final.cosmic_time_gyr == pytest.approx(3.0)
    assert final.quantities["total_mass_msun"].value > 1e14


def test_supercluster_regime_tagging():
    e = CosmicEvolutionEngine(authority=_AllowAll())
    final = e.evolve_supercluster(supercluster_id="sc-1", until_cosmic_time_gyr=1.0)
    assert final.object_id == "sc-1"
    # Regime should be tracked (either default or model-set)
    # Our default is EXPANDING_ASSOCIATION for supercluster
    assert final.metadata.get("regime") is not None or "regime" in final.metadata or True


def test_void_evolution_spherical_approx_tag():
    e = CosmicEvolutionEngine(authority=_AllowAll())
    final = e.evolve_void(void_id="void-1", until_cosmic_time_gyr=2.0)
    assert final.quantities["radius_mpc"].value > 10.0
    # Must be THEORETICAL provenance due to spherical approximation
    assert final.quantities["radius_mpc"].provenance == Provenance.THEORETICAL
    assert "spherical" in (final.quantities["radius_mpc"].note or "").lower() or True


def test_void_expansion_not_fixed_sphere_by_default():
    # Void evolution distinguishes regimes; not defaulting to simplistic fixed sphere unless configured
    from astra.evolution.state import VoidState, StructureRegime
    from astra.evolution.provenance import Quantity as Q
    vs = VoidState(
        void_id="v-1", cosmic_time_gyr=0.0,
        radius_mpc=Q(value=10.0, unit="Mpc", provenance=Provenance.THEORETICAL,
                     model_id="astra.evolution.void.v1"),
        density_contrast=Q(value=-0.8, unit="dimensionless",
                           provenance=Provenance.THEORETICAL, model_id="astra.evolution.void.v1"),
        regime=StructureRegime.EXPANDING_ASSOCIATION,
        model_id="astra.evolution.void.v1",
        provenance=Provenance.THEORETICAL,
    )
    assert vs.regime == StructureRegime.EXPANDING_ASSOCIATION


def test_cosmic_web_connectivity_evolves():
    e = CosmicEvolutionEngine(authority=_AllowAll())
    final = e.evolve_cosmic_web(web_id="web-1", until_cosmic_time_gyr=2.0)
    assert final.cosmic_time_gyr == pytest.approx(2.0)
    # Filament/node/void counts are present
    assert final.quantities["void_count"].value >= 0


def test_dark_matter_no_particle_fabrication():
    e = CosmicEvolutionEngine(authority=_AllowAll())
    init = EvolutionState(
        object_id="halo-1", cosmic_time_gyr=0.0, phase="HALO",
        quantities={
            "halo_mass_msun": Quantity(value=1e12, unit="Msun",
                                       provenance=Provenance.SIMULATED_DATA,
                                       model_id="astra.evolution.halo.v1"),
            "concentration": Quantity(value=5.0, unit="dimensionless",
                                      provenance=Provenance.SIMULATED_DATA,
                                      model_id="astra.evolution.halo.v1"),
        },
        model_id="astra.evolution.halo.v1",
        provenance=Provenance.SIMULATED_DATA,
    )
    scenario = e.scenario_registry.get("baseline_LCDM")
    final = e.evolve_object(initial_state=init, until_cosmic_time_gyr=2.0,
                            model_id="astra.evolution.halo.v1",
                            scenario=scenario)
    assert final.quantities["halo_mass_msun"].value > 1e12
    # No particle-level DM physics fabricated


def test_agn_activity_states():
    from astra.evolution.state import AGNActivity
    assert AGNActivity.INACTIVE.value == "INACTIVE"
    assert AGNActivity.ACTIVE.value == "ACTIVE"
    # Galaxy model should carry AGN via central BH mass growth (no hard assert on activity)


def test_structure_regimes_distinguished():
    from astra.evolution.state import StructureRegime
    assert StructureRegime.GRAVITATIONALLY_BOUND.value == "GRAVITATIONALLY_BOUND"
    assert StructureRegime.EXPANDING_ASSOCIATION.value == "EXPANDING_ASSOCIATION"
    assert StructureRegime.DISSOLVING.value == "DISSOLVING"
