"""Persistence round-trip — to_dict/from_dict preserves invariants."""

from astra.evolution.persistence import (
    state_to_dict, state_from_dict,
    event_to_dict, event_from_dict,
    quantity_to_dict, quantity_from_dict,
    sfh_to_dict, sfh_from_dict,
    population_to_dict, population_from_dict,
)
from astra.evolution.state import (
    EvolutionState, EvolutionEvent, EvolutionEventKind,
    StarFormationHistory, PopulationState,
)
from astra.evolution.provenance import Provenance, Quantity


def test_state_roundtrip():
    s = EvolutionState(
        object_id="o", cosmic_time_gyr=1.5, phase="X",
        quantities={"m": Quantity(value=1.0, unit="Msun", provenance=Provenance.SIMULATED_DATA)},
        model_id="toy", provenance=Provenance.SIMULATED_DATA,
    )
    d = state_to_dict(s)
    s2 = state_from_dict(d)
    assert s2.object_id == s.object_id
    assert s2.cosmic_time_gyr == s.cosmic_time_gyr
    assert state_to_dict(s2) == d
    assert s2.quantities["m"].value == s.quantities["m"].value


def test_event_roundtrip():
    e = EvolutionEvent(
        event_id="evt-1", kind=EvolutionEventKind.GALAXY_MERGER,
        cosmic_time_gyr=5.0,
        source_object_ids=("g1", "g2"), resulting_object_ids=("g3",),
        physical_cause="merger", model_id="toy",
        provenance=Provenance.SIMULATED_DATA,
        causal_parent_event_id="evt-0",
        metadata={"mass_ratio": 0.5},
    )
    d = event_to_dict(e)
    e2 = event_from_dict(d)
    assert e2.event_id == e.event_id
    assert e2.kind == e.kind
    assert event_to_dict(e2) == d


def test_quantity_roundtrip():
    q = Quantity(value=1.23, unit="Mpc", provenance=Provenance.THEORETICAL,
                 uncertainty=0.01, model_id="m", note="test")
    d = quantity_to_dict(q)
    q2 = quantity_from_dict(d)
    assert q2.value == q.value
    assert q2.unit == q.unit
    assert q2.provenance == q.provenance
    assert q2.uncertainty == q.uncertainty
    assert quantity_to_dict(q2) == d


def test_sfh_roundtrip():
    sfh = StarFormationHistory(
        object_id="g-1",
        samples=((0.0, 10.0), (1.0, 5.0), (13.8, 0.1)),
        model_id="toy", provenance=Provenance.SIMULATED_DATA,
    )
    d = sfh_to_dict(sfh)
    sfh2 = sfh_from_dict(d)
    assert sfh2.samples == sfh.samples
    assert sfh_to_dict(sfh2) == d


def test_population_roundtrip():
    pop = PopulationState(
        population_id="pop-1", cosmic_time_gyr=1.0, parent_object_id="gal-1",
        mass_function=((1.0, 0.5), (10.0, 0.1)),
        age_distribution=((0.1, 0.3), (1.0, 0.7)),
        remnant_fraction=0.2, metallicity=0.02,
        model_id="toy", provenance=Provenance.SIMULATED_DATA,
    )
    d = population_to_dict(pop)
    pop2 = population_from_dict(d)
    assert pop2.population_id == pop.population_id
    assert population_to_dict(pop2) == d


def test_determinism_across_serialization():
    s = EvolutionState(
        object_id="o", cosmic_time_gyr=1.5, phase="X",
        quantities={"m": Quantity(value=1.0, unit="Msun", provenance=Provenance.SIMULATED_DATA, uncertainty=0.01)},
        model_id="toy", provenance=Provenance.SIMULATED_DATA,
    )
    d1 = state_to_dict(s)
    d2 = state_to_dict(state_from_dict(d1))
    assert d1 == d2
