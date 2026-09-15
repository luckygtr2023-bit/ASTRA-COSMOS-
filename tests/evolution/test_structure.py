"""Phase 21 — structure, cluster, cosmic-web tests (spec 2.16-2.21)."""
from __future__ import annotations

import pytest

from astra.evolution import (
    CosmicEvolutionEngine,
    EvolutionConfig,
    EvolutionDependencyError,
    EvolutionLimitationError,
    Scenario,
    StructureRegime,
    classify_structure_regime,
    make_cluster_state,
    make_galaxy_state,
    make_web_state,
)


class AllowAll:
    def require(self, op):
        pass


WEB = "web.regime_evolution.v1"
CLUSTER = "cluster.member_aggregate.v1"


def _eng(resolution="web"):
    return CosmicEvolutionEngine(
        config=EvolutionConfig(resolution=resolution), authority=AllowAll()
    )


def _scenario(**kw):
    d = dict(scenario_id="s", name="S", description="")
    d.update(kw)
    return Scenario(**d)


# ------------------------------------------------------- regime classification
def test_regime_classification_from_binding_ratio():
    assert classify_structure_regime(binding_energy_ratio=2.0) is StructureRegime.GRAVITATIONALLY_BOUND
    assert classify_structure_regime(binding_energy_ratio=1.0) is StructureRegime.EXPANDING_ASSOCIATION
    assert classify_structure_regime(binding_energy_ratio=0.5) is StructureRegime.DISSOLVING


def test_regime_classification_refuses_missing_dynamics():
    """No binding input -> explicit refusal, never a bound assumption."""
    with pytest.raises(EvolutionLimitationError) as excinfo:
        classify_structure_regime(binding_energy_ratio=None)
    assert excinfo.value.state.value == "MISSING_REQUIRED_DATA"


# ------------------------------------------------------------- cosmic web
def test_web_requires_expansion_input():
    eng = _eng()
    with pytest.raises(EvolutionDependencyError):
        eng.evolve_cosmic_web(
            web_state=make_web_state("w", 0.0),
            until_cosmic_time_gyr=1.0,
            scenario=_scenario(),
        )


def test_web_proper_sizes_follow_supplied_ratio():
    """Phase 21 consumes the supplied scale-factor ratios; it never
    computes them (spec 2.22)."""
    eng = _eng()
    web = make_web_state("w", 0.0, void_size_comoving_mpc=30.0)
    ratios = []

    def expansion(t, dt):
        r = 1.0 + 0.01 * dt
        ratios.append(r)
        return r

    out = eng.evolve_cosmic_web(
        web_state=web, until_cosmic_time_gyr=10.0,
        scenario=_scenario(), expansion_ratio_fn=expansion,
    )
    assert ratios, "expansion function must be consulted every step"
    product = 1.0
    for r in ratios:
        product *= r
    expected = 30.0 * product
    assert out.final_state.quantity_value("void_size_proper_mpc") == pytest.approx(expected, rel=1e-9)
    assert out.final_state.quantity_value("void_size_comoving_mpc") == pytest.approx(30.0)


def test_web_regime_determines_sigma_evolution():
    eng = _eng()
    scenario = _scenario()

    def flat(t, dt):
        return 1.0

    bound = make_web_state("w-bound", 0.0, density_contrast_sigma=2.0)
    out_bound = eng.evolve_cosmic_web(
        web_state=bound, until_cosmic_time_gyr=5.0, scenario=scenario,
        expansion_ratio_fn=flat,
    )
    # Engine-level regime tag drives growth; default is EXPANDING (quenched).
    assert out_bound.final_state.quantity_value("density_contrast_sigma") == pytest.approx(2.0)

    dissolving = make_web_state("w-dis", 0.0, density_contrast_sigma=2.0)
    from dataclasses import replace as _replace

    dissolving = _replace(
        dissolving, metadata={**dissolving.metadata, "regime": StructureRegime.DISSOLVING.value}
    )
    out_dis = eng.evolve_cosmic_web(
        web_state=dissolving, until_cosmic_time_gyr=5.0, scenario=scenario,
        expansion_ratio_fn=flat,
    )
    assert out_dis.final_state.quantity_value("density_contrast_sigma") < 2.0


def test_web_hierarchical_inflow_and_void_growth():
    eng = _eng()
    web = make_web_state(
        "w", 0.0,
        node_fraction=0.05, filament_fraction=0.20, sheet_fraction=0.30,
        void_volume_fraction=0.60,
    )

    def flat(t, dt):
        return 1.0

    out = eng.evolve_cosmic_web(
        web_state=web, until_cosmic_time_gyr=20.0, scenario=_scenario(),
        expansion_ratio_fn=flat,
    )
    f = out.final_state
    assert f.quantity_value("node_mass_fraction") > 0.05
    assert f.quantity_value("sheet_mass_fraction") < 0.30
    assert f.quantity_value("void_volume_fraction") > 0.60
    # Mass fractions remain bounded.
    assert f.quantity_value("node_mass_fraction") + f.quantity_value("filament_mass_fraction") + f.quantity_value("sheet_mass_fraction") <= 1.0 + 1e-9


def test_web_universe_provider_path():
    """The injected UniverseEvolutionProvider supplies the ratio (the
    provider interface is consumption-only; Phase 21 never derives a)."""
    class ToyUniverse:
        def __init__(self):
            self.calls = 0

        def scale_factor(self, cosmic_time_gyr):
            self.calls += 1
            return 1.0 + 0.001 * cosmic_time_gyr

    eng = _eng()
    universe = ToyUniverse()
    eng3 = CosmicEvolutionEngine(
        config=EvolutionConfig(resolution="web"),
        authority=AllowAll(), universe=universe,
    )
    eng3.evolve_cosmic_web(
        web_state=make_web_state("w", 0.0), until_cosmic_time_gyr=2.0,
        scenario=_scenario(),
    )
    assert universe.calls > 0


def test_structure_regime_recording():
    eng = _eng()
    web = make_web_state("w", 0.0)
    event = eng.record_structure_regime(
        state=web, structure_id="supercluster-virgo-ish",
        binding_energy_ratio=3.0, cosmic_time_gyr=1.0,
    )
    assert event.kind.value == "COSMIC_STRUCTURE_TRANSITION"
    assert event.metadata["to"] == StructureRegime.GRAVITATIONALLY_BOUND.value


# ------------------------------------------------------------- clusters
def test_cluster_aggregates_members():
    eng = _eng(resolution="cluster")
    cluster = make_cluster_state("cl", 0.0, member_ids=("g1", "g2"), total_mass_msun=1e14)
    m1 = make_galaxy_state("g1", 0.0, stellar_mass_msun=5e10, gas_mass_msun=2e10, bh_mass_msun=1e7)
    m2 = make_galaxy_state("g2", 0.0, stellar_mass_msun=2e10, gas_mass_msun=5e9, bh_mass_msun=3e6)
    out = eng.evolve_cluster(
        cluster_state=cluster, member_states=[m2, m1],  # unsorted on purpose
        until_cosmic_time_gyr=5.0, scenario=_scenario(),
    )
    cf = out.cluster.final_state
    expected_stellar = (
        out.member_final_state("g1").quantity_value("stellar_mass_msun")
        + out.member_final_state("g2").quantity_value("stellar_mass_msun")
    )
    assert cf.quantity_value("stellar_mass_msun") == pytest.approx(expected_stellar)
    assert cf.quantity_value("member_count") == 2.0
    assert cf.quantity_value("total_mass_msun") == pytest.approx(1e14)


def test_cluster_member_not_listed_rejected():
    eng = _eng(resolution="cluster")
    cluster = make_cluster_state("cl", 0.0, member_ids=("g1",), total_mass_msun=1e14)
    stranger = make_galaxy_state("stranger", 0.0, stellar_mass_msun=1e10, gas_mass_msun=1e9)
    member = make_galaxy_state("g1", 0.0, stellar_mass_msun=1e10, gas_mass_msun=1e9)
    with pytest.raises(Exception):
        eng.evolve_cluster(
            cluster_state=cluster, member_states=[member, stranger],
            until_cosmic_time_gyr=1.0, scenario=_scenario(),
        )


def test_cluster_default_regime_is_unknown_not_bound():
    """Spec 2.17: structures are NOT assumed permanently bound; without
    dynamics the regime is honestly UNKNOWN."""
    cluster = make_cluster_state("cl", 0.0, member_ids=())
    assert cluster.metadata["regime"] == StructureRegime.UNKNOWN.value


def test_cluster_accretion_parameter_grows_mass():
    from astra.evolution import BuiltinModelParams

    params = BuiltinModelParams(cluster_accretion_msun_yr=10.0)  # 10 Msun/yr
    from astra.evolution import ModelRegistry, register_builtin_models

    reg = ModelRegistry()
    register_builtin_models(reg, params)
    eng = CosmicEvolutionEngine(
        config=EvolutionConfig(resolution="cluster"), model_registry=reg,
        register_builtins=False, authority=AllowAll(),
    )
    cluster = make_cluster_state("cl", 0.0, member_ids=(), total_mass_msun=1e14)
    out = eng.evolve_object(
        initial_state=cluster, until_cosmic_time_gyr=1.0,
        model_id=CLUSTER, scenario=_scenario(),
    )
    assert out.final_state.quantity_value("total_mass_msun") == pytest.approx(1e14 + 10.0 * 1e9)
