"""Observation + ingestion + cosmology integration tests."""
import pytest
from astra.galactic import GalacticEngine, GalacticConfig, Galaxy, GalaxyType, Vec3, CoordinateContext, Frame, Provenance, SimulatedValue
from astra.galactic.errors import GalacticDependencyError, GalacticValidationError, GalacticNumericalError

class _AllowAll:
    def require(self, op): return None

def _ctx():
    return CoordinateContext(frame=Frame.COMOVING, scale_factor=1.0, epoch_gyr=0.0)

def test_observe_galaxy_finite_light():
    e = GalacticEngine(config=GalacticConfig(), authority=_AllowAll())
    # place galaxy essentially at observer location so finite-light solve succeeds in short time
    # (100 Mpc would require ~1e16 s light travel; we use 0 distance for test)
    g = Galaxy(galaxy_id="g-1", name="G1", galaxy_type=GalaxyType.SPIRAL, position=Vec3(0,0,0), coordinate_context=_ctx())
    e.register_galaxy(g)
    # observe via engine — should go through ObservationProvider, not direct field access
    observed = e.observe_galaxy("observer-1", "g-1", observation_time_s=10.0)
    assert observed is not None
    # lookback position also available
    lb = e.lookback_position("observer-1", "g-1", at_time_s=10.0)
    assert lb is not None


def test_observe_unknown_galaxy_rejected():
    e = GalacticEngine(config=GalacticConfig(), authority=_AllowAll())
    with pytest.raises(GalacticValidationError):
        e.observe_galaxy("obs", "nope", 0)


def test_cosmological_distance_lowz():
    e = GalacticEngine(config=GalacticConfig(), authority=_AllowAll())
    from astra.galactic.types import DistanceKind
    d = e.cosmological_distance(0.1, DistanceKind.COMOVING)
    assert d > 0
    # proper < comoving for z>0
    dc = e.cosmological_distance(0.5, DistanceKind.COMOVING)
    dp = e.cosmological_distance(0.5, DistanceKind.PROPER)
    assert dp < dc


def test_redshift_scale_factor_inverse():
    e = GalacticEngine(config=GalacticConfig(), authority=_AllowAll())
    sf = e.redshift_to_scale_factor(1.0)
    assert sf == pytest.approx(0.5)


def test_matter_sampling_lazy():
    e = GalacticEngine(config=GalacticConfig(), authority=_AllowAll())
    ctx = _ctx()
    pos = Vec3(0,0,0)
    s = e.get_density_at(pos, ctx)
    assert hasattr(s.density_kg_m3, "value")
    assert s.density_kg_m3.value > 0
    # clustered model uses galaxy proximity
    e.register_galaxy(Galaxy(galaxy_id="g-1", name="G1", galaxy_type=GalaxyType.SPIRAL, position=Vec3(0,0,0), coordinate_context=ctx))
    samples = e.sample_matter_distribution([Vec3(0,0,0), Vec3(100,0,0)], ctx, model="clustered")
    assert len(samples) == 2
    # near galaxy should be denser than far
    assert samples[0].density_kg_m3.value > samples[1].density_kg_m3.value


def test_ingestion_build_adql():
    e = GalacticEngine(config=GalacticConfig(), authority=_AllowAll())
    from astra.ingestion.query import GaiaQuerySpec
    spec = GaiaQuerySpec(min_parallax_mas=1.0)
    adql = e.build_gaia_adql(spec)
    assert "SELECT" in adql
    assert "parallax" in adql


def test_ingestion_query_raises_not_fabricate():
    e = GalacticEngine(config=GalacticConfig(), authority=_AllowAll())
    with pytest.raises(GalacticDependencyError):
        e.ingestion_query("gaia", {})


def test_blackhole_ref_validation():
    e = GalacticEngine(config=GalacticConfig(), authority=_AllowAll())
    g = Galaxy(galaxy_id="g-bh", name="GBH", galaxy_type=GalaxyType.ELLIPTICAL, position=Vec3(0,0,0), coordinate_context=_ctx(), central_black_hole_ref="bh-123")
    e.register_galaxy(g)
    assert e.get_galaxy("g-bh").central_black_hole_ref == "bh-123"
    # empty ref should be rejected at Galaxy construction
    with pytest.raises(GalacticValidationError):
        Galaxy(galaxy_id="g-bad", name="GBAD", galaxy_type=GalaxyType.SPIRAL, position=Vec3(0,0,0), coordinate_context=_ctx(), central_black_hole_ref="")


def test_hierarchy_depth_guard():
    from astra.galactic.types import HierarchyRelation
    e = GalacticEngine(config=GalacticConfig(), authority=_AllowAll())
    # create deep chain exceeding max_hierarchy_depth (6)
    for i in range(7):
        e.link(f"node-{i}", f"node-{i+1}", HierarchyRelation.CONTAINS)
    with pytest.raises(Exception):
        e.hierarchy_depth("node-0")


def test_coordinate_context_required_for_distance():
    e = GalacticEngine(config=GalacticConfig(), authority=_AllowAll())
    from astra.galactic.types import DistanceKind
    a = Vec3(0,0,0)
    b = Vec3(1,0,0)
    ctx = _ctx()
    assert e.distance(a,b,ctx,DistanceKind.PROPER) == pytest.approx(1.0)
    # invalid ctx should raise
    with pytest.raises(Exception):
        e.distance(a,b, None, DistanceKind.PROPER)  # type: ignore
