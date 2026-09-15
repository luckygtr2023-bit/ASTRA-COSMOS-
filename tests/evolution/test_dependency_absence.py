"""Phase 21 — dependency-absence tests: missing ASTRA systems must fail
LOUDLY, never silently substitute (spec rule 5; handoff 4.5)."""
from __future__ import annotations

import pytest

from astra.evolution import (
    CosmicEvolutionEngine,
    EvolutionConfig,
    EvolutionDependencyError,
    Scenario,
    make_web_state,
)


@pytest.mark.parametrize("adapter_name,attr", [
    ("MissingUniverseEvolution", "scale_factor"),
    ("MissingUniverseEvolution", "hubble_parameter"),
    ("MissingGalactic", "get_galaxy"),
    ("MissingGalactic", "get_cluster"),
    ("MissingGalactic", "get_cosmic_web"),
    ("MissingStellar", "get_star"),
    ("MissingBlackHole", "get_black_hole"),
    ("MissingNBody", "potential_energy"),
    ("MissingTemporal", "register_event"),
    ("MissingObservation", "lookback_state"),
    ("MissingMeasurement", "measure"),
])
def test_missing_dependency_raises(adapter_name, attr):
    import astra.evolution as evo

    adapter = getattr(evo, adapter_name)()
    with pytest.raises(EvolutionDependencyError):
        getattr(adapter, attr)


def test_missing_adapter_names_the_absent_system():
    from astra.evolution import MissingUniverseEvolution

    adapter = MissingUniverseEvolution()
    with pytest.raises(EvolutionDependencyError) as excinfo:
        adapter.scale_factor
    assert "universe evolution" in str(excinfo.value).lower()


def test_web_evolution_refuses_without_expansion_source():
    """No Universe Evolution in repo: cosmic-web evolution without an
    injected provider or caller function refuses explicitly."""
    class AllowAll:
        def require(self, op):
            pass

    eng = CosmicEvolutionEngine(config=EvolutionConfig(resolution="web"), authority=AllowAll())
    with pytest.raises(EvolutionDependencyError):
        eng.evolve_cosmic_web(
            web_state=make_web_state("w", 0.0), until_cosmic_time_gyr=1.0,
            scenario=Scenario(scenario_id="s", name="S", description=""),
        )


def test_save_refuses_without_persistence_hook():
    class AllowAll:
        def require(self, op):
            pass

    eng = CosmicEvolutionEngine(authority=AllowAll())
    with pytest.raises(EvolutionDependencyError):
        eng.save("snap")


def test_engine_never_imports_absent_modules():
    """Structural guarantee: no direct import of systems that do not exist
    (verified also by the harness grep sweep)."""
    import pathlib

    package = pathlib.Path(__file__).resolve().parents[2] / "astra" / "evolution"
    forbidden = (
        "universe_evolution", "galactic", "observatory", "measurement",
        "cosmology", "large_scale_structure",
    )
    for path in package.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")):
                for name in forbidden:
                    assert name not in stripped, (
                        f"{path.name}: direct import touching absent system "
                        f"'{name}': {stripped}"
                    )
