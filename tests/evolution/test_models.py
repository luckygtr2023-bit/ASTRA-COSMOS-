"""Phase 21 — model registry tests: registration, deterministic query,
assumptions, scenario overrides."""
from __future__ import annotations

import pytest

from astra.evolution import (
    BuiltinModelParams,
    DataProvenance,
    EvolutionModel,
    EvolutionValidationError,
    ModelAssumption,
    ModelClassification,
    ModelRegistry,
    Scenario,
    register_builtin_models,
)


def _step(s, dt, m):
    return s


def _model(mid, kinds=("GALAXY",), regimes=("STELLIFEROUS",)):
    return EvolutionModel(
        model_id=mid,
        name=mid,
        description="test model",
        classification=ModelClassification.SIMULATION,
        provenance=DataProvenance.SIMULATED_DATA,
        applicable_object_kinds=kinds,
        applies_to_regimes=regimes,
    )


def test_register_and_get():
    r = ModelRegistry()
    r.register(_model("m1"), _step)
    assert r.get("m1").model_id == "m1"
    assert r.step_for("m1") is _step


def test_duplicate_rejected():
    r = ModelRegistry()
    r.register(_model("m1"), _step)
    with pytest.raises(EvolutionValidationError):
        r.register(_model("m1"), _step)


def test_unknown_model_and_missing_step():
    r = ModelRegistry()
    with pytest.raises(EvolutionValidationError):
        r.get("ghost")
    with pytest.raises(EvolutionValidationError):
        r.step_for("ghost")


def test_query_by_kind_and_regime():
    r = ModelRegistry()
    r.register(_model("a", ("GALAXY",), ("STELLIFEROUS",)), _step)
    r.register(_model("b", ("CLUSTER",), ("DEGENERATE",)), _step)
    r.register(_model("c", ("GALAXY",), ("DEGENERATE",)), _step)
    assert [m.model_id for m in r.query(object_kind="GALAXY")] == ["a", "c"]
    assert [m.model_id for m in r.query(regime="DEGENERATE")] == ["b", "c"]
    both = [m.model_id for m in r.query(object_kind="GALAXY", regime="DEGENERATE")]
    assert both == ["c"]


def test_query_ordering_deterministic():
    r = ModelRegistry()
    for mid in ["z", "a", "m"]:
        r.register(_model(mid, (), ()), _step)
    assert [m.model_id for m in r.query()] == ["a", "m", "z"]


def test_query_by_classification_and_provenance():
    r = ModelRegistry()
    r.register(_model("sim1"), _step)
    speculative = EvolutionModel(
        model_id="spec1",
        name="spec",
        description="speculative extrapolation",
        classification=ModelClassification.SPECULATIVE,
        provenance=DataProvenance.SPECULATIVE_MODEL,
        applicable_object_kinds=("GALAXY",),
    )
    r.register(speculative, _step)
    got = r.query(classification=ModelClassification.SPECULATIVE)
    assert [m.model_id for m in got] == ["spec1"]
    got2 = r.query(provenance=DataProvenance.SPECULATIVE_MODEL)
    assert [m.model_id for m in got2] == ["spec1"]


def test_model_metadata_validation():
    with pytest.raises(EvolutionValidationError):
        _model("")  # empty id
    with pytest.raises(EvolutionValidationError):
        EvolutionModel(
            model_id="m", name="m", description="",
            classification=ModelClassification.SIMULATION,
            provenance=DataProvenance.SIMULATED_DATA,
        )
    with pytest.raises(EvolutionValidationError):
        EvolutionModel(
            model_id="m", name="m", description="d",
            classification=ModelClassification.SIMULATION,
            provenance=DataProvenance.SIMULATED_DATA,
            max_valid_cosmic_time_gyr=-1.0,
        )


def test_assumption_entries_validated():
    with pytest.raises(EvolutionValidationError):
        ModelAssumption(statement="", valid_regime="x", outside_behaviour="y")


def test_metadata_round_trip_without_step():
    """Model METADATA serializes; step callables are code and are NOT
    serialized (documented persistence boundary)."""
    r = ModelRegistry()
    register_builtin_models(r, BuiltinModelParams())
    model = r.get("galaxy.one_zone.v1")
    d = model.to_dict()
    model2 = EvolutionModel.metadata_from_dict(d)
    assert model2.model_id == model.model_id
    assert model2.classification is model.classification
    assert model2.to_dict() == d
    assert model2.rate_scale is None  # callables never travel through dicts


def test_builtin_models_registered_with_assumptions():
    r = ModelRegistry()
    register_builtin_models(r, BuiltinModelParams())
    for mid in (
        "stellar.single_star_lifecycle.v1",
        "population.conveyor.v1",
        "galaxy.one_zone.v1",
        "cluster.member_aggregate.v1",
        "web.regime_evolution.v1",
    ):
        model = r.get(mid)
        assert model.assumptions, f"{mid} must state assumptions"
        assert model.description
        assert model.max_valid_cosmic_time_gyr is not None
        assert model.applicable_object_kinds


def test_scenario_parameter_override_mechanism():
    """Scenario evolution_parameters override same-named model parameters."""
    eng_params = BuiltinModelParams(gas_depletion_time_gyr=2.0)
    r = ModelRegistry()
    register_builtin_models(r, eng_params)
    model = r.get("galaxy.one_zone.v1")
    scenario = Scenario(
        scenario_id="highsf",
        name="High SF",
        description="short depletion time",
        evolution_parameters={
            "gas_depletion_time_gyr": __import__(
                "astra.evolution", fromlist=["Quantity"]
            ).Quantity(value=0.5, unit="Gyr"),
        },
    )
    from astra.evolution.engine import CosmicEvolutionEngine

    class AllowAll:
        def require(self, op):
            pass

    eng = CosmicEvolutionEngine(
        model_registry=r, authority=AllowAll(), register_builtins=False
    )
    effective = eng._effective_model(model, scenario)
    assert effective.parameters["gas_depletion_time_gyr"].value == 0.5
    assert model.parameters["gas_depletion_time_gyr"].value == 2.0  # registry untouched

    bad = Scenario(
        scenario_id="bad",
        name="Bad",
        description="",
        evolution_parameters={"not_a_param": __import__(
            "astra.evolution", fromlist=["Quantity"]).Quantity(value=1.0, unit="1")},
    )
    with pytest.raises(EvolutionValidationError):
        eng._effective_model(model, bad)
