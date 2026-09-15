"""Performance smoke test."""
import time

import pytest

from astra.galactic import GalacticConfig, GalacticEngine, Galaxy, GalaxyType, Vec3, CoordinateContext, Frame


class _AllowAll:
    def require(self, operation): return None


def _ctx():
    return CoordinateContext(Frame.COMOVING, 1.0, 0.0)


def test_register_10k_galaxies_under_budget():
    e = GalacticEngine(config=GalacticConfig(), authority=_AllowAll())
    t0 = time.perf_counter()
    for i in range(10_000):
        e.register_galaxy(Galaxy(
            galaxy_id=f"g-{i}", name=f"G{i}", galaxy_type=GalaxyType.SPIRAL,
            position=Vec3(float(i), 0.0, 0.0),
            coordinate_context=_ctx(),
        ))
    dt_ms = (time.perf_counter() - t0) * 1000
    # budget is 10_000 ms for cosmic web build, 100ms for query, but 10k inserts should be <2s
    assert dt_ms < 2000.0, f"registration too slow: {dt_ms:.0f} ms"
    # diagnostics should reflect count
    assert e.diagnostics()["galaxies"] == 10_000


def test_spatial_query_performance():
    e = GalacticEngine(config=GalacticConfig(), authority=_AllowAll())
    for i in range(5_000):
        e.register_galaxy(Galaxy(
            galaxy_id=f"g-{i}", name=f"G{i}", galaxy_type=GalaxyType.ELLIPTICAL,
            position=Vec3(float(i % 100), float(i // 100), 0.0),
            coordinate_context=_ctx(),
        ))
    t0 = time.perf_counter()
    res = e.query_galaxies_in_radius(Vec3(50, 25, 0), radius_mpc=10.0)
    dt_ms = (time.perf_counter() - t0) * 1000
    assert dt_ms < 100.0, f"radius query too slow: {dt_ms:.0f} ms"
    assert len(res) > 0


def test_matter_sampling_no_dense_array():
    e = GalacticEngine(config=GalacticConfig(), authority=_AllowAll())
    ctx = _ctx()
    # sample 1000 sparse points — should not allocate dense 3D array
    positions = [Vec3(float(i), 0, 0) for i in range(1000)]
    t0 = time.perf_counter()
    samples = e.sample_matter_distribution(positions, ctx, model="uniform")
    dt_ms = (time.perf_counter() - t0) * 1000
    assert len(samples) == 1000
    # ensure no dense allocation: we just check it completes quickly
    assert dt_ms < 500.0


def test_hierarchy_traversal_under_budget():
    e = GalacticEngine(config=GalacticConfig(), authority=_AllowAll())
    # build chain p->c1->c2... but depth limited to 6, so make star
    e.register_galaxy(Galaxy(galaxy_id="g-0", name="G0", galaxy_type=GalaxyType.SPIRAL, position=Vec3(0,0,0), coordinate_context=_ctx()))
    for i in range(1, 1000):
        e.register_galaxy(Galaxy(galaxy_id=f"g-{i}", name=f"G{i}", galaxy_type=GalaxyType.SPIRAL, position=Vec3(float(i),0,0), coordinate_context=_ctx()))
        e.link("root", f"g-{i}", __import__("astra.galactic.types", fromlist=["HierarchyRelation"]).HierarchyRelation.CONTAINS)
    t0 = time.perf_counter()
    children = e.hierarchy_children("root")
    dt_ms = (time.perf_counter() - t0) * 1000
    assert len(children) == 999
    assert dt_ms < 1000.0
