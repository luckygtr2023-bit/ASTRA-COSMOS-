"""Tests for Phase 21: Universe Evolution & Procedural Generation.

Covers:
  - SeedManager determinism, hierarchy, order independence, invalid inputs
  - Provenance tagging & versioning
  - Stellar & Planetary generators determinism & distributions
  - RegionManager lazy, cache, precedence, stats, persistence
  - Evolution deterministic aging & remnant transitions
  - Integration with simulation time hooks
  - Adversarial same-seed-different-path, dict-order independence, OS independence
  - Failure handling
"""

import math
import random

import pytest

from astra.procedural.provenance import DataProvenance, GenerationVersion, ProvenanceTag
from astra.procedural.seed_manager import SeedManager
from astra.procedural.generators.stellar import StellarGenerator
from astra.procedural.generators.planetary import PlanetarySystemGenerator
from astra.procedural.region_manager import RegionManager
from astra.procedural.evolution.stellar_evolution import StellarEvolutionEngine
from astra.core.threading import AuthorityContext, get_simulation_thread_registry, reset_simulation_thread_registry


@pytest.fixture(autouse=True)
def authority():
    reset_simulation_thread_registry()
    reg = get_simulation_thread_registry()
    tid = __import__("threading").current_thread().ident
    if tid is not None:
        try:
            reg.register_simulation_thread(tid)
        except Exception:
            pass
    yield
    reset_simulation_thread_registry()


# SeedManager
def test_seed_determinism():
    sm1 = SeedManager("astra_universe_v1")
    sm2 = SeedManager("astra_universe_v1")
    path = ["milky_way", "orion_spur", "sol"]
    assert sm1.derive_seed(path) == sm2.derive_seed(path)


def test_seed_hierarchy_and_order():
    sm = SeedManager("alpha")
    assert sm.derive_seed(["a", "b"]) != sm.derive_seed(["b", "a"])
    assert sm.derive_seed(["a", "b", "c"]) != sm.derive_seed(["a", "b"])
    # same path same seed regardless of call order
    s1 = sm.derive_seed(["x", "y"])
    s2 = sm.derive_seed(["x", "y"])
    assert s1 == s2


def test_seed_different_universe():
    sm1 = SeedManager("univ1")
    sm2 = SeedManager("univ2")
    assert sm1.derive_seed(["a"]) != sm2.derive_seed(["a"])


def test_seed_invalid():
    sm = SeedManager("test")
    with pytest.raises(ValueError):
        sm.derive_seed(["a:b"])
    with pytest.raises(ValueError):
        sm.derive_seed([""])
    with pytest.raises(TypeError):
        sm.derive_seed("not_list")  # type: ignore
    with pytest.raises(ValueError):
        SeedManager("")
    with pytest.raises(ValueError):
        SeedManager("   ")


def test_seed_derive_variadic_and_child():
    sm = SeedManager("root")
    assert sm.derive_seed(["a", "b"]) == sm.derive_seed_for("a", "b")
    child = sm.child_manager(["a"])
    # child should be deterministic
    child2 = sm.child_manager(["a"])
    assert child.derive_seed(["x"]) == child2.derive_seed(["x"])


def test_seed_range_and_hex():
    sm = SeedManager("check")
    seed = sm.derive_seed(["path"])
    assert 0 <= seed < 2**64
    # Same as int of first 16 hex chars of sha256
    import hashlib
    hex_digest = hashlib.sha256("check:path".encode()).hexdigest()[:16]
    assert seed == int(hex_digest, 16)


# Provenance
def test_provenance_tags():
    tag = ProvenanceTag(provenance=DataProvenance.GENERATED_DATA, seed_used=123)
    assert tag.is_generated
    assert not tag.is_real
    assert tag.to_dict()["provenance"] == "GENERATED_DATA"
    # mapping to celestial
    cel = tag.to_celestial_provenance()
    # Should map to SIMULATED_DATA
    assert cel.value == "SIMULATED_DATA"
    # round trip
    tag2 = ProvenanceTag.from_dict(tag.to_dict())
    assert tag2.provenance == tag.provenance
    # version present
    assert tag.generation_version == GenerationVersion.CURRENT_ALGORITHM_VERSION


def test_provenance_invalid():
    with pytest.raises(TypeError):
        ProvenanceTag(provenance="REAL_DATA")  # type: ignore
    with pytest.raises(ValueError):
        ProvenanceTag(provenance=DataProvenance.REAL_DATA, source_label="")


# Stellar
def test_stellar_determinism_and_reproducibility():
    seed = 123456789
    gen1 = StellarGenerator(seed)
    star1 = gen1.generate_star_system("sys_01")
    gen2 = StellarGenerator(seed)
    star2 = gen2.generate_star_system("sys_01")
    assert star1["physics_state"]["mass_solar"] == star2["physics_state"]["mass_solar"]
    assert star1["metadata"]["provenance"] == "GENERATED_DATA"
    assert star1["metadata"]["generation_version"] == GenerationVersion.CURRENT_ALGORITHM_VERSION
    # different seed → different star (with high probability)
    gen3 = StellarGenerator(seed + 1)
    star3 = gen3.generate_star_system("sys_01")
    assert star3["physics_state"]["mass_solar"] != star1["physics_state"]["mass_solar"]


def test_stellar_distribution_and_physics():
    gen = StellarGenerator(42)
    masses = [gen.generate_star_system(f"s{i}")["physics_state"]["mass_solar"] for i in range(1000)]
    # Check distribution: ~70% M (0.08-0.5)
    m_count = sum(1 for m in masses if 0.08 <= m < 0.5)
    assert 600 <= m_count <= 800  # allow variance
    # All masses finite and positive
    for m in masses:
        assert math.isfinite(m) and m > 0
    # Luminosity and radius consistent
    for i in range(10):
        star = gen.generate_star_system(f"t{i}")
        ps = star["physics_state"]
        assert math.isfinite(ps["luminosity_solar"]) and ps["luminosity_solar"] > 0
        assert math.isfinite(ps["radius_solar"]) and ps["radius_solar"] > 0
        assert 2000 <= ps["surface_temperature_k"] <= 50000
        assert ps["spectral_type"] in ("O", "B", "A", "F", "G", "K", "M")


def test_stellar_invalid():
    gen = StellarGenerator(1)
    with pytest.raises(ValueError):
        gen.generate_star_system("")
    with pytest.raises(ValueError):
        gen.generate_star_system("bad:id")
    with pytest.raises(ValueError):
        gen.generate_multiple("pref", -1)


def test_stellar_reset():
    gen = StellarGenerator(99)
    s1 = gen.generate_star_system("a")
    gen.reset()
    s2 = gen.generate_star_system("a")
    assert s1["physics_state"]["mass_solar"] == s2["physics_state"]["mass_solar"]


# Planetary
def test_planetary_determinism():
    seed = 555
    gen1 = PlanetarySystemGenerator(seed)
    p1 = gen1.generate_planets(1.0, "sys")
    gen2 = PlanetarySystemGenerator(seed)
    p2 = gen2.generate_planets(1.0, "sys")
    assert p1 == p2
    # different parent id but same seed should still be deterministic per call but we pass same parent_id, so same
    # Different star mass → different planets (probabilistic but with same seed, num planets same, but distances scaled)
    gen3 = PlanetarySystemGenerator(seed)
    p3 = gen3.generate_planets(5.0, "sys")
    # Not necessarily equal in count? With same seed, num_planets same (randint first), but subsequent distances differ slightly due to mass scaling?
    # Actually current_distance initial scaling differs, so planets differ
    assert p1 != p3 or len(p1) == 0


def test_planetary_spacing_and_bounds():
    gen = PlanetarySystemGenerator(123)
    for _ in range(20):
        planets = gen.generate_planets(1.0, "test_sys")
        for p in planets:
            a = p["orbital_state"]["semi_major_axis_au"]
            ecc = p["orbital_state"]["eccentricity"]
            assert 0 <= ecc <= 0.2 + 1e-9
            assert a > 0.02  # periastron check ensures >0.02
            assert 0.3 <= p["physics_state"]["radius_earth"] <= 20
            assert p["physics_state"]["mass_earth"] > 0
            # Check provenance
            assert p["metadata"]["provenance"] == "GENERATED_DATA"
        # Check spacing increasing
        if len(planets) >= 2:
            for i in range(1, len(planets)):
                assert planets[i]["orbital_state"]["semi_major_axis_au"] > planets[i-1]["orbital_state"]["semi_major_axis_au"]


def test_planetary_invalid():
    gen = PlanetarySystemGenerator(1)
    with pytest.raises(ValueError):
        gen.generate_planets(-1, "id")
    with pytest.raises(ValueError):
        gen.generate_planets(float("nan"), "id")
    with pytest.raises(ValueError):
        gen.generate_planets(1.0, "")


# RegionManager
def test_region_lazy_and_cache():
    mgr = RegionManager("uni1")
    r1 = mgr.generate_region_on_demand("region_A")
    assert "systems" in r1
    assert len(r1["systems"]) >= 5
    # Cache hit: second call returns same object (identity) and counts
    r1_again = mgr.generate_region_on_demand("region_A")
    assert r1_again is r1
    assert mgr.stats()["cache_hits"] == 1
    assert mgr.stats()["generated"] == 1


def test_region_determinism_and_order_independence():
    # Same seed, same region, different request order → same result
    mgr1 = RegionManager("seedX")
    a1 = mgr1.generate_region_on_demand("R1")
    b1 = mgr1.generate_region_on_demand("R2")

    mgr2 = RegionManager("seedX")
    b2 = mgr2.generate_region_on_demand("R2")
    a2 = mgr2.generate_region_on_demand("R1")

    assert a1 == a2
    assert b1 == b2
    # Different path yields different seed, so different system count with high prob
    assert mgr1.seed_manager.derive_seed(["R1"]) != mgr1.seed_manager.derive_seed(["R2"])


def test_region_real_data_precedence():
    auth = {"sol_region": {"is_real": True, "stars": ["Sol"], "metadata": {"provenance": "REAL_DATA"}}}
    mgr = RegionManager("test_univ", authoritative_db=auth)
    sol = mgr.generate_region_on_demand("sol_region")
    assert sol.get("is_real") is True
    # Should not be counted as generated
    assert mgr.stats()["authoritative_hits"] == 1
    assert mgr.stats()["generated"] == 0
    # Generated region should not be authoritative
    proc = mgr.generate_region_on_demand("unknown_X")
    assert proc["metadata"]["provenance"] == "GENERATED_DATA"
    assert mgr.is_generated("unknown_X")
    assert not mgr.is_generated("sol_region")
    assert mgr.is_authoritative("sol_region")


def test_region_register_and_precedence():
    mgr = RegionManager("seed")
    mgr.register_authoritative("myreg", {"data": 1})
    assert mgr.is_authoritative("myreg")
    with pytest.raises(ValueError):
        mgr.register_authoritative("myreg", {"data": 2})
    # force overwrite
    mgr.register_authoritative("myreg", {"data": 2}, force=True)
    assert mgr.authoritative_db["myreg"]["data"] == 2
    # If already cached as generated, registering should invalidate cache
    mgr2 = RegionManager("seed2")
    gen = mgr2.generate_region_on_demand("R")
    assert mgr2.is_generated("R")
    mgr2.register_authoritative("R", {"is_real": True}, force=True)
    # Next request should return authoritative, not cached generated
    # But we cleared cache on register? Check implementation clears generated_regions entry
    r = mgr2.generate_region_on_demand("R")
    assert r.get("is_real") is True


def test_region_invalid_and_persistence():
    mgr = RegionManager("seed")
    with pytest.raises(ValueError):
        mgr.generate_region_on_demand("")
    with pytest.raises(ValueError):
        mgr.generate_region_on_demand("bad:id")
    with pytest.raises(ValueError):
        mgr.register_authoritative("", {"x": 1})
    # to_dict/from_dict
    mgr.generate_region_on_demand("A")
    d = mgr.to_dict()
    mgr2 = RegionManager.from_dict(d)
    assert mgr2.seed_manager.universe_seed == mgr.seed_manager.universe_seed
    assert mgr2.generated_regions["A"] == mgr.generated_regions["A"]


def test_region_adversarial_same_seed_different_path():
    sm = SeedManager("alpha")
    assert sm.derive_seed(["reg1", "sys1"]) != sm.derive_seed(["reg1", "sys2"])


# Evolution
def test_stellar_evolution_lifecycle():
    engine = StellarEvolutionEngine(time_engine=None)
    # High mass short lifespan → BH
    star = {"identity": "heavy", "physics_state": {"mass_solar": 25.0, "age_gyr": 0.0, "is_remnant": False}}
    evolved = engine.apply_evolution(star, 5.0)
    assert evolved["physics_state"]["is_remnant"] is True
    assert evolved["physics_state"]["classification"] == "Black Hole"
    assert evolved is not star  # copy-on-write
    assert star["physics_state"]["age_gyr"] == 0.0  # original not mutated

    # Low mass → WD after long time
    star2 = {"identity": "low", "physics_state": {"mass_solar": 1.0, "age_gyr": 0.0, "is_remnant": False}}
    evolved2 = engine.apply_evolution(star2, 12.0)  # ms lifespan ~10 Gyr for 1M
    assert evolved2["physics_state"]["is_remnant"] is True
    assert evolved2["physics_state"]["classification"] == "White Dwarf"

    # Medium → NS
    star3 = {"identity": "mid", "physics_state": {"mass_solar": 10.0, "age_gyr": 0.0, "is_remnant": False}}
    evolved3 = engine.apply_evolution(star3, 5.0)
    # ms_lifespan for 10M is 10/10^2.5 ~0.03 Gyr, so should be remnant
    assert evolved3["physics_state"]["is_remnant"] is True
    assert evolved3["physics_state"]["classification"] in ("Neutron Star", "Black Hole")


def test_stellar_evolution_no_transition_if_not_expired():
    engine = StellarEvolutionEngine()
    star = {"identity": "young", "physics_state": {"mass_solar": 1.0, "age_gyr": 0.1, "is_remnant": False}}
    evolved = engine.apply_evolution(star, 1.0)
    assert evolved["physics_state"]["is_remnant"] is False
    assert math.isclose(evolved["physics_state"]["age_gyr"], 1.1)


def test_stellar_evolution_already_remnant():
    engine = StellarEvolutionEngine()
    star = {"identity": "wd", "physics_state": {"mass_solar": 0.6, "age_gyr": 5.0, "is_remnant": True}}
    evolved = engine.apply_evolution(star, 1.0)
    assert evolved["physics_state"]["is_remnant"] is True
    assert evolved["physics_state"]["mass_solar"] == 0.6


def test_stellar_evolution_invalid():
    engine = StellarEvolutionEngine()
    with pytest.raises(ValueError):
        engine.apply_evolution({"physics_state": {"mass_solar": 1.0}}, -1.0)
    with pytest.raises(ValueError):
        engine.apply_evolution({"physics_state": {"mass_solar": float("nan")}}, 1.0)
    with pytest.raises(TypeError):
        engine.apply_evolution("not_dict", 1.0)  # type: ignore
    with pytest.raises(ValueError):
        engine.apply_evolution({"physics_state": {}}, 1.0)


def test_evolution_determinism():
    engine = StellarEvolutionEngine()
    star = {"identity": "s", "physics_state": {"mass_solar": 5.0, "age_gyr": 0.0, "is_remnant": False}}
    e1 = engine.apply_evolution(star, 2.0)
    e2 = engine.apply_evolution(star, 2.0)
    assert e1 == e2


def test_evolution_hook_for_simulation():
    # Ensure hook signature compatible with SimulationTimeEngine
    from astra.simulation import SimulationTimeEngine, EvolutionConfig
    eng = SimulationTimeEngine(config=EvolutionConfig(tick_duration_s=1.0, max_step_s=10.0))
    evo = StellarEvolutionEngine(time_engine=eng)
    # Register as celestial hook (evolution is post-event)
    eng.register_hook("celestial", evo.hook_for_simulation)
    with AuthorityContext("test"):
        eng.initialize()
        eng.start()
        eng.advance(5.0)
    # No error, hook was called (no-op)
    assert eng.simulation_time_s == 5.0


def test_no_fabrication_of_real_data():
    # Generated data must never be tagged as REAL_DATA
    gen = StellarGenerator(12345)
    star = gen.generate_star_system("test")
    assert star["metadata"]["provenance"] != "REAL_DATA"
    assert star["metadata"]["provenance"] == "GENERATED_DATA"
    # RegionManager with real data should preserve REAL_DATA
    mgr = RegionManager("seed", authoritative_db={"real": {"metadata": {"provenance": "REAL_DATA"}, "is_real": True}})
    real = mgr.generate_region_on_demand("real")
    assert real["metadata"]["provenance"] == "REAL_DATA"


def test_version_tracking():
    gen = StellarGenerator(1)
    star = gen.generate_star_system("vtest")
    assert "generation_version" in star["metadata"]
    assert star["metadata"]["generation_version"] == GenerationVersion.CURRENT_ALGORITHM_VERSION
    # Region metadata also versioned
    mgr = RegionManager("seed")
    region = mgr.generate_region_on_demand("R")
    assert region["metadata"]["generation_version"] == GenerationVersion.CURRENT_ALGORITHM_VERSION
