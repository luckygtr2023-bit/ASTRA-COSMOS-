"""Proves that missing dependencies fail loudly, not silently."""
import pytest

from astra.galactic.errors import GalacticDependencyError
from astra.galactic.adapters import MissingCosmology, MissingNBody, MissingObservation, MissingCoordinates, MissingMeasurement, MissingIngestion, MissingBlackHole


def test_missing_cosmology_raises_on_use():
    m = MissingCosmology()
    with pytest.raises(GalacticDependencyError):
        m.scale_factor(1.0)
    with pytest.raises(GalacticDependencyError):
        m.comoving_distance(0.5)


def test_missing_nbody_raises_on_use():
    m = MissingNBody()
    with pytest.raises(GalacticDependencyError):
        m.potential_at((0, 0, 0))
    with pytest.raises(GalacticDependencyError):
        m.gravity_at((0,0,0))


def test_missing_observation_raises_on_use():
    m = MissingObservation()
    with pytest.raises(GalacticDependencyError):
        m.redshift(None, "g-1")
    with pytest.raises(GalacticDependencyError):
        m.lookback_position(None, "g-1", 0)


def test_missing_coordinates_raises():
    m = MissingCoordinates()
    with pytest.raises(GalacticDependencyError):
        m.transform((0,0,0), "a", "b")


def test_missing_measurement_raises():
    m = MissingMeasurement()
    with pytest.raises(GalacticDependencyError):
        m.measure_position(None, "g-1")


def test_missing_ingestion_raises():
    m = MissingIngestion()
    with pytest.raises(GalacticDependencyError):
        m.query_catalog("gaia", {})


def test_missing_blackhole_raises():
    m = MissingBlackHole()
    with pytest.raises(GalacticDependencyError):
        m.get_black_hole("bh-1")


def test_default_cosmology_limited_range():
    from astra.galactic.integration import DefaultCosmologyProvider
    from astra.galactic.errors import GalacticLimitationError
    c = DefaultCosmologyProvider()
    # high z out of low-z validity should raise
    with pytest.raises(GalacticLimitationError):
        c.comoving_distance(10.0)


def test_engine_with_missing_cosmology_still_works_for_galaxies():
    from astra.galactic import GalacticEngine, GalacticConfig
    from astra.galactic.adapters import MissingCosmology
    class _AllowAll:
        def require(self, op): return None
    e = GalacticEngine(config=GalacticConfig(), authority=_AllowAll(), cosmology=MissingCosmology())
    # galaxy registration should still work even if cosmology missing
    from astra.galactic.types import Galaxy, GalaxyType, Vec3, CoordinateContext, Frame
    g = Galaxy(galaxy_id="g-1", name="G1", galaxy_type=GalaxyType.SPIRAL, position=Vec3(0,0,0), coordinate_context=CoordinateContext(Frame.COMOVING, 1.0, 0.0))
    e.register_galaxy(g)
    assert e.get_galaxy("g-1").galaxy_id == "g-1"
    # but cosmological_distance should raise
    from astra.galactic.types import DistanceKind
    with pytest.raises(GalacticDependencyError):
        e.cosmological_distance(0.5, DistanceKind.COMOVING)
