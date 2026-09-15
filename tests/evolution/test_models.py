"""Model registry tests — registration, deterministic query, classification."""

import pytest

from astra.evolution import (
    EvolutionValidationError,
    ModelClassification,
    ModelRegistry,
    EvolutionModel,
    Provenance,
    Quantity,
    ModelAssumption,
)


def _step(s, dt, m):
    return s


def test_register_and_get():
    r = ModelRegistry()
    m = EvolutionModel(
        model_id="m1", name="M1", description="",
        classification=ModelClassification.SIMULATION,
        provenance=Provenance.SIMULATED_DATA,
        applicable_object_kinds=("GALAXY",),
        applies_to_regimes=("STELLIFEROUS",),
    )
    r.register(m, _step)
    assert r.get("m1").model_id == "m1"
    assert r.step_for("m1") is _step


def test_duplicate_rejected():
    r = ModelRegistry()
    m = EvolutionModel(model_id="m1", name="M1", description="",
                       classification=ModelClassification.SIMULATION,
                       provenance=Provenance.SIMULATED_DATA)
    r.register(m, _step)
    with pytest.raises(EvolutionValidationError):
        r.register(m, _step)


def test_unknown_model_rejected():
    r = ModelRegistry()
    with pytest.raises(EvolutionValidationError):
        r.get("nope")
    with pytest.raises(EvolutionValidationError):
        r.step_for("nope")


def test_query_by_kind_and_regime():
    r = ModelRegistry()
    for mid, kinds, regimes in [
        ("a", ("GALAXY",), ("STELLIFEROUS",)),
        ("b", ("CLUSTER",), ("DEGENERATE",)),
        ("c", ("GALAXY",), ("DEGENERATE",)),
    ]:
        r.register(EvolutionModel(
            model_id=mid, name=mid, description="",
            classification=ModelClassification.SIMULATION,
            provenance=Provenance.SIMULATED_DATA,
            applicable_object_kinds=kinds,
            applies_to_regimes=regimes,
        ), _step)
    assert [m.model_id for m in r.query(object_kind="GALAXY")] == ["a", "c"]
    assert [m.model_id for m in r.query(regime="DEGENERATE")] == ["b", "c"]
    assert [m.model_id for m in r.query(object_kind="GALAXY", regime="DEGENERATE")] == ["c"]


def test_query_by_classification_and_provenance():
    r = ModelRegistry()
    for mid, cls_, prov in [
        ("sim", ModelClassification.SIMULATION, Provenance.SIMULATED_DATA),
        ("theo", ModelClassification.THEORETICAL, Provenance.THEORETICAL),
        ("spec", ModelClassification.SPECULATIVE, Provenance.SPECULATIVE),
    ]:
        r.register(EvolutionModel(
            model_id=mid, name=mid, description="",
            classification=cls_, provenance=prov,
        ), _step)
    assert [m.model_id for m in r.query(classification=ModelClassification.SIMULATION)] == ["sim"]
    assert [m.model_id for m in r.query(provenance=Provenance.SPECULATIVE)] == ["spec"]


def test_query_ordering_deterministic():
    r = ModelRegistry()
    for mid in ["z", "a", "m"]:
        r.register(EvolutionModel(
            model_id=mid, name=mid, description="",
            classification=ModelClassification.SIMULATION,
            provenance=Provenance.SIMULATED_DATA,
        ), _step)
    assert [m.model_id for m in r.query()] == ["a", "m", "z"]
    # second call identical
    assert [m.model_id for m in r.query()] == ["a", "m", "z"]


def test_model_assumption_validation():
    # Valid assumption
    a = ModelAssumption(
        statement="Valid for 0<z<6",
        valid_regime="z < 6",
        outside_behaviour="flag HYPOTHETICAL",
        uncertainty=0.2,
    )
    assert a.uncertainty == 0.2
    # Negative uncertainty rejected
    with pytest.raises(EvolutionValidationError):
        ModelAssumption(
            statement="x", valid_regime="x", outside_behaviour="y",
            uncertainty=-1.0,
        )


def test_model_parameters_carry_provenance():
    m = EvolutionModel(
        model_id="param-test", name="P", description="",
        classification=ModelClassification.SIMULATION,
        provenance=Provenance.SIMULATED_DATA,
        parameters={
            "tau": Quantity(value=5.0, unit="Gyr", provenance=Provenance.SIMULATED_DATA),
        },
    )
    assert m.parameters["tau"].provenance == Provenance.SIMULATED_DATA
    assert m.parameters["tau"].value == 5.0


def test_scenario_registry_query():
    from astra.evolution import Scenario, ScenarioRegistry
    reg = ScenarioRegistry()
    for sid, prov in [("a", Provenance.SIMULATED_DATA), ("b", Provenance.SPECULATIVE)]:
        reg.register(Scenario(scenario_id=sid, name=sid, description="",
                              cosmological_parameters={}, evolution_parameters={},
                              provenance=prov, model_version="v1"))
    assert reg.get("a").scenario_id == "a"
    assert len(reg.query(provenance=Provenance.SPECULATIVE)) == 1
    assert reg.query(provenance=Provenance.SPECULATIVE)[0].scenario_id == "b"
