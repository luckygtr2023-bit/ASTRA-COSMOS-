"""Missing dependencies must fail loudly — no silent stubs."""

import pytest

from astra.evolution.adapters import (
    MissingUniverseEvolution, MissingGalactic, MissingStellar,
    MissingBlackHole, MissingNBody, MissingTemporal,
    MissingObservation, MissingMeasurement,
)
from astra.evolution.errors import EvolutionDependencyError


@pytest.mark.parametrize("adapter,method,args", [
    (MissingUniverseEvolution(), "scale_factor", (1.0,)),
    (MissingGalactic(), "get_galaxy", ("g-1",)),
    (MissingStellar(), "get_star", ("s-1",)),
    (MissingBlackHole(), "get_black_hole", ("bh-1",)),
    (MissingNBody(), "potential_at", ((0, 0, 0),)),
    (MissingTemporal(), "register_event", (None,)),
    (MissingObservation(), "lookback_state", (None, "o-1", 1.0)),
    (MissingMeasurement(), "measure", (None, "o-1")),
])
def test_missing_dependency_raises(adapter, method, args):
    with pytest.raises(EvolutionDependencyError):
        getattr(adapter, method)(*args)


def test_universe_provider_absent_raises_on_scale_factor():
    from astra.evolution import CosmicEvolutionEngine

    class _AllowAll:
        def require(self, op): return None
        def has_authority(self, op): return True

    e = CosmicEvolutionEngine(authority=_AllowAll())
    with pytest.raises(EvolutionDependencyError):
        e.scale_factor(13.8)


def test_galactic_absent_uses_reduced_order():
    """Evolving a galaxy without a GalacticProvider should still succeed via reduced-order model."""
    from astra.evolution import CosmicEvolutionEngine, Provenance

    class _AllowAll:
        def require(self, op): return None
        def has_authority(self, op): return True

    e = CosmicEvolutionEngine(authority=_AllowAll())
    # No galactic provider injected — uses default galaxy model
    final = e.evolve_galaxy(galaxy_id="g-test", until_cosmic_time_gyr=1.0)
    assert final.cosmic_time_gyr == pytest.approx(1.0)
    assert final.provenance in (Provenance.SIMULATED_DATA, Provenance.THEORETICAL)


def test_no_direct_universe_import():
    """Verify ABSENT dependencies are not directly imported at top level."""
    import ast
    import pathlib
    evo = pathlib.Path("astra/evolution")
    absent_tokens = ["astra.universe", "astra.galactic"]
    for py in evo.glob("*.py"):
        text = py.read_text()
        for tok in absent_tokens:
            # allow comments, but not import statements
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("import ") or stripped.startswith("from "):
                    assert tok not in line, f"{py.name}: direct import of ABSENT {tok} found: {line!r}"
