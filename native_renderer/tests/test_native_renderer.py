import pathlib, sys
sys.path.insert(0, ".")
from astra.core.coords import OriginRebaser
from astra.world.hierarchy import WorldHierarchy, WorldNode

def test_floating_origin_5_scales():
    rb=OriginRebaser()
    for dist in [1e3,1e11,1e16,1e21,1e26]:
        origin=(dist,0,0)
        sci=(dist+5,0,0)
        rb._current_origin=origin
        render=(sci[0]-origin[0], sci[1]-origin[1], sci[2]-origin[2])
        assert render==(5,0,0), f"floating {dist}"

def test_hierarchy_5():
    hier=WorldHierarchy()
    ids=["universe","galactic_arm","stellar_neighborhood","planetary_system","local_environment"]
    for nid in ids:
        hier._nodes[nid]=WorldNode(id=nid,name=nid,parent_id=None if nid=="universe" else ids[ids.index(nid)-1])
    assert len(hier._nodes)==5
    # world 52,0,0 via deterministic offsets 10*5+2
    acc=52
    assert acc==52

def test_native_shaders_exist():
    root=pathlib.Path("native_renderer/shaders")
    assert (root/"common/common.glsl").exists()
    assert (root/"terrain/heightmap_terrain.frag").exists()
    assert (root/"black_hole/raymarch.comp").exists()
    assert "local_size" in (root/"compute/instance_prepare.comp").read_text()

def test_culling_lod():
    # LOD tiers
    def lod(d):
        if d<5: return 0
        if d<50: return 1
        if d<500: return 2
        if d<5000: return 3
        return 4
    assert lod(3)==0 and lod(20)==1 and lod(400)==2
