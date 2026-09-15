"""Round-trip persistence tests."""
from astra.galactic.persistence import galaxy_to_dict, galaxy_from_dict, edge_to_dict, edge_from_dict, web_to_dict, web_from_dict
from astra.galactic.types import Galaxy, GalaxyType, CoordinateContext, Frame, Vec3, CosmicWeb, HierarchyEdge, HierarchyRelation


def _g():
    return Galaxy(
        galaxy_id="g-1", name="G1", galaxy_type=GalaxyType.SPIRAL,
        position=Vec3(1.0, 2.0, 3.0),
        coordinate_context=CoordinateContext(Frame.COMOVING, 1.0, 0.0),
    )


def test_galaxy_roundtrip():
    d = galaxy_to_dict(_g())
    g = galaxy_from_dict(d)
    assert g.galaxy_id == "g-1"
    assert g.position.to_tuple() == (1.0, 2.0, 3.0)
    assert galaxy_to_dict(g) == d


def test_galaxy_deterministic_dict():
    g1 = _g()
    g2 = Galaxy(galaxy_id="g-1", name="G1", galaxy_type=GalaxyType.SPIRAL, position=Vec3(1,2,3), coordinate_context=CoordinateContext(Frame.COMOVING,1.0,0.0))
    assert galaxy_to_dict(g1) == galaxy_to_dict(g2)


def test_edge_roundtrip():
    e = HierarchyEdge(parent_id="p1", child_id="c1", relation=HierarchyRelation.CONTAINS)
    d = edge_to_dict(e)
    e2 = edge_from_dict(d)
    assert e == e2
    assert edge_to_dict(e2) == d


def test_web_roundtrip():
    w = CosmicWeb(web_id="web-1", node_ids=("n-2","n-1"), filament_ids=("f-2","f-1"), sheet_ids=(), void_ids=("v-1",))
    d = web_to_dict(w)
    w2 = web_from_dict(d)
    assert w2.web_id == "web-1"
    # dict roundtrip deterministic (web stores tuples, but dict uses lists)
    assert web_to_dict(w2) == d


def test_engine_save_load_roundtrip():
    from astra.galactic import GalacticEngine, GalacticConfig
    class _AllowAll:
        def require(self, op): return None
    e = GalacticEngine(config=GalacticConfig(), authority=_AllowAll())
    g = _g()
    e.register_galaxy(g)
    e.link("p", "g-1", HierarchyRelation.CONTAINS)
    # save to persistence hook
    e.save("test-key")
    data = e.load("test-key")
    assert "galaxies" in data
    assert len(data["galaxies"]) == 1
    # ensure sorted order in payload
    assert data["galaxies"][0]["galaxy_id"] == "g-1"
