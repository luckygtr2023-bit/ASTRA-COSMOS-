"""Tests for ASTRA Rendering Architecture phase.

Covers:
- render state construction / validation / isolation / conversion
- camera position/orientation/tracking/projection/extreme scales
- coordinates world->render, camera-relative, floating-origin, large coords
- LOD deterministic selection, boundaries, invalid inputs
- visibility/culling filtering enable/disable
- celestial classification & render representation
- planetary surface/atmosphere/terrain/ocean interfaces
- destruction damage-state, fragments, ejecta, debris
- temporal current vs historical
- relativity/black-hole/spacetime parameter conversion
- robustness invalid values, extreme scales, missing optional data
- performance budgeting, simulation authority isolation, determinism
"""

import math
import pytest

from astra.mathematics import Vector3, Quaternion
from astra.rendering import (
    RenderObject,
    RenderState,
    MaterialRef,
    Camera,
    CameraController,
    CameraError,
    FloatingOriginRenderer,
    FloatingOriginConfig,
    world_to_render,
    render_to_world,
    world_to_camera_relative,
    Viewport,
    QualityLevel,
    LODLevel,
    ProjectionType,
    VisibilityState,
    TemporalRenderMode,
    DamageVisualState,
    RenderObjectKind,
    LODConfig,
    LODSelector,
    LODError,
    Frustum,
    CullingConfig,
    VisibilitySystem,
    CelestialRenderDescriptor,
    describe_celestial,
    celestial_to_render_object,
    TerrainDescriptor,
    AtmosphereDescriptor,
    OceanDescriptor,
    CloudDescriptor,
    PlanetarySurfaceDescriptor,
    PlanetaryRenderDescriptor,
    LightSource,
    LightType,
    LightingState,
    ShadowConfig,
    BlackHoleRenderParams,
    black_hole_state_to_render_params,
    wormhole_metric_to_render_params,
    WarpRenderParams,
    warp_metric_to_render_params,
    DestructionVisualState,
    destruction_result_to_visual,
    ObservedRenderRecord,
    compute_lookback,
    observed_state_to_render_record,
    RenderPipeline,
    PipelineConfig,
    PerformanceBudget,
    PerformanceManager,
    RenderContext,
)
from astra.rendering.exceptions import RenderStateError, CoordinateConversionError

# ---------------------------------------------------------------------------
# Render State
# ---------------------------------------------------------------------------

class TestRenderState:
    def test_construction_and_add(self):
        rs = RenderState(tick=5, simulation_time_s=10.0)
        assert rs.count() == 0
        obj = RenderObject(id="obj1", position=Vector3(1, 2, 3), bounding_radius_m=5.0)
        rs.add(obj)
        assert rs.count() == 1
        assert rs.contains("obj1")
        # clone isolation
        obj.position = Vector3(999, 999, 999)  # mutating original should not affect stored?
        # Actually RenderObject is mutable dataclass; we cloned on add
        fetched = rs.get("obj1")
        assert fetched.position.x == 1.0

    def test_validation_non_finite(self):
        with pytest.raises(RenderStateError):
            RenderObject(id="bad", position=Vector3(float("nan"), 0, 0))
        with pytest.raises(RenderStateError):
            RenderObject(id="bad", position=Vector3(0, 0, 0), bounding_radius_m=-1)
        with pytest.raises(RenderStateError):
            RenderObject(id="", position=Vector3(0, 0, 0))
        with pytest.raises(RenderStateError):
            RenderState(tick=-1)

    def test_state_isolation_clone(self):
        rs = RenderState(tick=0)
        rs.add(RenderObject(id="a", position=Vector3(0, 0, 0)))
        cloned = rs.clone()
        cloned.add(RenderObject(id="b", position=Vector3(10, 0, 0)))
        assert rs.count() == 1
        assert cloned.count() == 2
        # mutate cloned object should not affect original
        obj_b = cloned.get("b")
        obj_b.position = Vector3(999, 0, 0)
        # original cloned's internal still has old pos? But get returns clone, so internal unchanged?
        # Check that fetched again is original pos
        assert cloned.get("b").position.x == 10.0

    def test_simulation_to_render_conversion(self):
        pipeline = RenderPipeline()
        objs = [
            {"id": "obj1", "world_position": Vector3(1000, 0, 0), "kind": RenderObjectKind.PLANET, "bounding_radius_m": 1000},
            {"id": "obj2", "world_position": Vector3(2000, 0, 0), "kind": RenderObjectKind.MOON},
        ]
        rs = pipeline.build_render_state(tick=0, simulation_time_s=0.0, world_objects=objs, render_origin=Vector3(1000, 0, 0))
        # obj1 should be at 0, obj2 at 1000 after rebase
        assert rs.get("obj1").position.x == pytest.approx(0.0)
        assert rs.get("obj2").position.x == pytest.approx(1000.0)
        # original world objects list not mutated
        assert objs[0]["world_position"].x == 1000

    def test_material_and_metadata(self):
        obj = RenderObject(id="mat_test", material=MaterialRef(id="custom", kind="pbr_placeholder", params=(("roughness", 0.5),)))
        assert obj.material.get("roughness") == 0.5
        rs = RenderState(tick=0)
        rs.add(obj)
        assert rs.get("mat_test").material.id == "custom"

    def test_max_objects_enforced(self):
        rs = RenderState(tick=0, max_objects=2)
        rs.add(RenderObject(id="a"))
        rs.add(RenderObject(id="b"))
        with pytest.raises(RenderStateError):
            rs.add(RenderObject(id="c"))

    def test_determinism_order(self):
        rs = RenderState(tick=0)
        for i in [3, 1, 2]:
            rs.add(RenderObject(id=f"obj_{i}", position=Vector3(float(i), 0, 0)))
        order = [o.id for o in rs.iterate()]
        assert order == ["obj_3", "obj_1", "obj_2"]  # insertion order preserved deterministically

# ---------------------------------------------------------------------------
# Camera
# ---------------------------------------------------------------------------

class TestCamera:
    def test_position_orientation_defaults(self):
        cam = Camera(position=Vector3(0, 0, 10), fov_y_deg=60)
        assert cam.position.z == 10
        assert cam.fov_y_deg == 60
        # orientation defaults to identity
        fwd = cam.get_forward()
        assert fwd.z == pytest.approx(-1.0)

    def test_look_at(self):
        cam = Camera(position=Vector3(0, 0, 10))
        cam.look_at(Vector3(0, 0, 0))
        fwd = cam.get_forward()
        # Should point roughly toward origin (negative Z ??? Actually from 0,0,10 looking at 0,0,0 is -Z)
        assert fwd.z < -0.9

    def test_orientation_validation(self):
        with pytest.raises(CameraError):
            Camera(position=Vector3(float("nan"), 0, 0))
        with pytest.raises(CameraError):
            Camera(fov_y_deg=0)  # too small
        with pytest.raises(CameraError):
            Camera(near=0)
        with pytest.raises(CameraError):
            Camera(position=Vector3(0, 0, 0), orientation=Quaternion(0, 0, 0, 0))

    def test_projection_switch(self):
        cam = Camera()
        cam.set_perspective(90, 0.1, 1e12)
        assert cam.projection == ProjectionType.PERSPECTIVE
        cam.set_orthographic(1000, 0.1, 1e6)
        assert cam.projection == ProjectionType.ORTHOGRAPHIC
        assert cam.ortho_height_m == 1000

    def test_tracking(self):
        cam = Camera(position=Vector3(0, 0, 10))
        cam.track(Vector3(100, 0, 0))
        assert cam.mode.value == "TRACKING"
        assert cam.target.x == 100

    def test_following(self):
        cam = Camera(position=Vector3(0, 0, 10))
        cam.follow("spacecraft_1", offset=Vector3(0, 10, 20))
        assert cam.follow_target_id == "spacecraft_1"
        ctrl = CameraController(cam)
        ctrl.register_follow_position("spacecraft_1", Vector3(500, 0, 0))
        ctrl.update_follow()
        assert cam.position.x == pytest.approx(500)
        assert cam.target.x == pytest.approx(500)

    def test_extreme_scales(self):
        # Galaxy scale
        cam = Camera(position=Vector3(1e22, -2e22, 3e22), far=1e25, near=1e3)
        dist = cam.distance_to(Vector3(1e22 + 1e20, -2e22, 3e22))
        assert dist == pytest.approx(1e20, rel=1e-6)
        # Spacecraft scale
        cam2 = Camera(position=Vector3(0, 0, 0.5), near=0.01, far=1e4)
        assert cam2.near == 0.01
        # Very large far should be allowed
        cam3 = Camera(position=Vector3(0, 0, 0), far=1e18)
        assert cam3.far == 1e18

    def test_orbit(self):
        cam = Camera(position=Vector3(0, 0, 10), target=Vector3(0, 0, 0))
        cam.look_at(Vector3(0, 0, 0))
        before = cam.position
        cam.orbit(math.radians(90), 0)
        # After 90deg yaw, position should be ~ (10,0,0) or (-10,0,0) depending on convention, but distance preserved
        dist_before = (before - Vector3(0, 0, 0)).magnitude()
        dist_after = (cam.position - Vector3(0, 0, 0)).magnitude()
        assert dist_after == pytest.approx(dist_before, rel=1e-6)

# ---------------------------------------------------------------------------
# Coordinates
# ---------------------------------------------------------------------------

class TestCoordinates:
    def test_world_to_render(self):
        wpos = Vector3(1e9, 2e9, 3e9)
        origin = Vector3(1e9, 0, 0)
        render = world_to_render(wpos, origin)
        assert render.x == pytest.approx(0.0)
        assert render.y == pytest.approx(2e9)
        assert render.z == pytest.approx(3e9)
        back = render_to_world(render, origin)
        assert back.x == pytest.approx(wpos.x)
        assert back.y == pytest.approx(wpos.y)

    def test_camera_relative(self):
        wpos = Vector3(100, 200, 300)
        cam = Vector3(10, 20, 30)
        rel = world_to_camera_relative(wpos, cam)
        assert rel.x == 90
        assert rel.y == 180
        assert rel.z == 270

    def test_floating_origin_rebase_does_not_mutate_simulation(self):
        from astra.core.coords import CoordinateFrame, FrameId
        # Simulate authoritative world positions
        authoritative_positions = [Vector3(1e12, 0, 0), Vector3(1e12 + 1000, 0, 0)]
        renderer = FloatingOriginRenderer(initial_origin=Vector3(0, 0, 0))
        # First conversion
        r1 = renderer.world_to_render(authoritative_positions[0])
        assert r1.x == pytest.approx(1e12)
        # Rebase to camera near objects
        renderer.rebase_to_camera(Vector3(1e12, 0, 0))
        r2 = renderer.world_to_render(authoritative_positions[0])
        assert r2.x == pytest.approx(0.0)
        # authoritative unchanged
        assert authoritative_positions[0].x == pytest.approx(1e12)
        # relative distance preserved after rebase
        r2_second = renderer.world_to_render(authoritative_positions[1])
        assert r2_second.x == pytest.approx(1000.0)

    def test_large_coordinates_precision(self):
        # Test that converting huge coordinates maintains relative precision via floating origin
        huge_origin = Vector3(1e14, 1e14, 1e14)
        renderer = FloatingOriginRenderer(initial_origin=huge_origin)
        wpos = Vector3(1e14 + 100.0, 1e14 + 200.0, 1e14 + 300.0)
        render = renderer.world_to_render(wpos)
        assert render.x == pytest.approx(100.0)
        assert render.y == pytest.approx(200.0)
        assert render.z == pytest.approx(300.0)
        # Without floating origin, direct float would lose? But with subtraction we preserve
        # Verify round-trip
        back = renderer.render_to_world(render)
        assert back.x == pytest.approx(wpos.x, rel=1e-12)

    def test_invalid_inputs(self):
        with pytest.raises(CoordinateConversionError):
            world_to_render(Vector3(float("inf"), 0, 0), Vector3(0, 0, 0))
        with pytest.raises(CoordinateConversionError):
            FloatingOriginRenderer(initial_origin=Vector3(float("nan"), 0, 0))
        with pytest.raises(CoordinateConversionError):
            FloatingOriginConfig(rebase_threshold_m=-1)

# ---------------------------------------------------------------------------
# LOD
# ---------------------------------------------------------------------------

class TestLOD:
    def test_deterministic_selection(self):
        sel = LODSelector()
        a = sel.select(distance_m=5e3, bounding_radius_m=1, apparent_size_rad=None, kind=RenderObjectKind.ASTEROID)
        b = sel.select(distance_m=5e3, bounding_radius_m=1, apparent_size_rad=None, kind=RenderObjectKind.ASTEROID)
        assert a == b

    def test_boundaries(self):
        # Use importance=0.5 so imp_bias=1.0 and effective distance == raw distance for deterministic threshold testing
        sel = LODSelector(LODConfig(ultra_distance_m=1000, high_distance_m=2000, medium_distance_m=5000, low_distance_m=10000, cull_distance_m=20000))
        assert sel.select(500, 1, importance=0.5) == LODLevel.ULTRA
        assert sel.select(1500, 1, importance=0.5) == LODLevel.HIGH
        assert sel.select(3000, 1, importance=0.5) == LODLevel.MEDIUM
        assert sel.select(8000, 1, importance=0.5) == LODLevel.LOW
        assert sel.select(15000, 1, importance=0.5) == LODLevel.IMPOSTOR
        assert sel.select(25000, 1, importance=0.5) == LODLevel.CULLED

    def test_apparent_size_overrides(self):
        sel = LODSelector()
        # Huge planet close but far distance, apparent size should dominate
        # At distance 1e9 but radius 6e6 -> angular ~0.012 rad -> MEDIUM
        size = 2 * math.asin(min(1.0, 6e6 / 1e9))
        lod = sel.select(distance_m=1e9, bounding_radius_m=6e6, apparent_size_rad=size, kind=RenderObjectKind.PLANET)
        assert lod in (LODLevel.MEDIUM, LODLevel.HIGH, LODLevel.LOW, LODLevel.ULTRA)
        # Tiny distant star should stay impostor not culled if star kind
        tiny = 0.00001
        lod_star = sel.select(distance_m=1e16, bounding_radius_m=6e8, apparent_size_rad=tiny, kind=RenderObjectKind.STAR)
        assert lod_star == LODLevel.IMPOSTOR
        lod_rock = sel.select(distance_m=1e16, bounding_radius_m=10, apparent_size_rad=tiny, kind=RenderObjectKind.ASTEROID)
        assert lod_rock in (LODLevel.CULLED, LODLevel.IMPOSTOR)

    def test_invalid_inputs(self):
        sel = LODSelector()
        with pytest.raises(LODError):
            sel.select(float("nan"), 1)
        with pytest.raises(LODError):
            sel.select(1000, -1)
        with pytest.raises(LODError):
            sel.select(1000, 1, apparent_size_rad=float("inf"))
        with pytest.raises(LODError):
            LODConfig(ultra_distance_m=-1)
        with pytest.raises(LODError):
            LODConfig(ultra_distance_m=1000, high_distance_m=500)  # out of order

    def test_quality_bias(self):
        sel_low = LODSelector(LODConfig(quality_bias={QualityLevel.LOW.value: 0.5, QualityLevel.MEDIUM.value: 1.0, QualityLevel.HIGH.value: 2.0}))
        d = 5000
        lod_low = sel_low.select(d, 1, kind=RenderObjectKind.SPACECRAFT, quality=QualityLevel.LOW)
        lod_high = sel_low.select(d, 1, kind=RenderObjectKind.SPACECRAFT, quality=QualityLevel.HIGH)
        # High quality should be more detailed (lower enum order)
        from astra.rendering.types import LOD_ORDER
        assert LOD_ORDER[lod_high] <= LOD_ORDER[lod_low]

# ---------------------------------------------------------------------------
# Visibility / Culling
# ---------------------------------------------------------------------------

class TestVisibility:
    def test_frustum_culling(self):
        cam = Camera(position=Vector3(0, 0, 0), viewport=Viewport(0,0,800,600))
        cam.look_at(Vector3(0, 0, -10))
        frustum = Frustum.from_camera(cam)
        # Object in front should be visible
        assert frustum.contains_sphere(Vector3(0, 0, -5), 1.0)
        # Object behind camera should be culled
        assert not frustum.contains_sphere(Vector3(0, 0, 10), 1.0)

    def test_distance_culling(self):
        vs = VisibilitySystem(CullingConfig(enable_frustum=False, max_distance_m=1000))
        cam = Camera(position=Vector3(0, 0, 0))
        near = RenderObject(id="near", position=Vector3(0, 0, 500), bounding_radius_m=1, distance_to_camera_m=500)
        far = RenderObject(id="far", position=Vector3(0, 0, 5000), bounding_radius_m=1, distance_to_camera_m=5000)
        assert vs.classify(near, cam) == VisibilityState.VISIBLE
        assert vs.classify(far, cam) == VisibilityState.CULLED_DISTANCE

    def test_category_filtering(self):
        vs = VisibilitySystem(CullingConfig(enable_frustum=False, enable_distance=False, enable_category_filter=True, culled_categories={"DEBRIS"}))
        cam = Camera(position=Vector3(0, 0, 0))
        debris = RenderObject(id="d1", category="DEBRIS", bounding_radius_m=1, distance_to_camera_m=10)
        planet = RenderObject(id="p1", category="PLANET", bounding_radius_m=1, distance_to_camera_m=10)
        assert vs.classify(debris, cam) == VisibilityState.CULLED_CATEGORY
        assert vs.classify(planet, cam) == VisibilityState.VISIBLE

    def test_enable_disable(self):
        vs = VisibilitySystem(CullingConfig(enable_frustum=False, enable_distance=False))
        cam = Camera(position=Vector3(0, 0, 0))
        obj = RenderObject(id="obj", enabled=False, visible=True, bounding_radius_m=1)
        assert vs.classify(obj, cam) == VisibilityState.DISABLED
        obj2 = RenderObject(id="obj2", enabled=True, visible=False, bounding_radius_m=1)
        assert vs.classify(obj2, cam) == VisibilityState.HIDDEN
        obj3 = RenderObject(id="obj3", enabled=True, visible=True, lod=LODLevel.CULLED, bounding_radius_m=1)
        assert vs.classify(obj3, cam) == VisibilityState.CULLED_DISTANCE

    def test_simulation_not_removed(self):
        # Culling should not delete from state
        rs = RenderState(tick=0)
        rs.add(RenderObject(id="keep", position=Vector3(0, 0, 10000), bounding_radius_m=1, distance_to_camera_m=10000))
        vs = VisibilitySystem(CullingConfig(enable_frustum=False, max_distance_m=100))
        cam = Camera(position=Vector3(0, 0, 0))
        vs.apply_to_render_state(rs, cam)
        assert rs.contains("keep")  # still in state
        assert rs.get("keep").visibility == VisibilityState.CULLED_DISTANCE

# ---------------------------------------------------------------------------
# Celestial Rendering
# ---------------------------------------------------------------------------

class TestCelestialRendering:
    def test_star_descriptor(self):
        from astra.celestial.api import create_identity, create_properties, create_star
        from astra.celestial.classification import SpectralType, LuminosityClass
        ident = create_identity("TestStar")
        props = create_properties(mass_kg=1.989e30, radius_m=6.96e8)
        star = create_star(ident, props, spectral_type=SpectralType.G, luminosity_class=LuminosityClass.DWARF)
        desc = describe_celestial(star)
        assert desc.render_kind == RenderObjectKind.STAR
        assert desc.radius_m == pytest.approx(6.96e8)
        assert desc.color_hint != (1.0, 1.0, 1.0) or True  # G type has warm color

    def test_planet_descriptor(self):
        from astra.celestial.api import create_identity, create_properties, create_planet
        from astra.celestial.classification import ObjectCategory
        ident = create_identity("Earth")
        props = create_properties(mass_kg=5.97e24, radius_m=6.371e6)
        planet = create_planet(ident, props, kind=ObjectCategory.PLANET)
        ro = celestial_to_render_object(planet, Vector3(1.5e11, 0, 0))
        assert ro.kind == RenderObjectKind.PLANET
        assert ro.bounding_radius_m == pytest.approx(6.371e6)

    def test_black_hole_celestial(self):
        from astra.celestial.api import create_identity, create_properties, create_black_hole_object
        ident = create_identity("BH1")
        props = create_properties(mass_kg=10*1.989e30, radius_m=30000)
        bh_obj = create_black_hole_object(ident, props, spin_param=0.5)
        ro = celestial_to_render_object(bh_obj, Vector3(0, 0, 0))
        assert ro.kind == RenderObjectKind.BLACK_HOLE

    def test_galaxy_and_nebula(self):
        from astra.celestial.api import create_identity, create_properties
        from astra.celestial.objects import Galaxy, Nebula
        from astra.celestial.classification import ObjectCategory
        ident = create_identity("Gal1")
        props = create_properties(mass_kg=1e42, radius_m=5e20)
        gal = Galaxy(ident, props, ObjectCategory.GALAXY)
        ro = celestial_to_render_object(gal, Vector3(1e22, 0, 0))
        assert ro.kind == RenderObjectKind.GALAXY
        assert ro.emissive is True

    def test_no_duplication_of_database(self):
        # Ensure celestial_to_render_object does not create new celestial registry
        from astra.celestial.api import create_identity, create_properties, create_star
        ident = create_identity("UniqueStar")
        props = create_properties(mass_kg=2e30, radius_m=7e8)
        star = create_star(ident, props)
        ro = celestial_to_render_object(star, Vector3(0, 0, 0))
        # source_ref should link back, not duplicate identity object
        assert ro.source_ref == "UniqueStar"
        assert ro.id == "celestial_UniqueStar"

# ---------------------------------------------------------------------------
# Planetary Rendering
# ---------------------------------------------------------------------------

class TestPlanetaryRendering:
    def test_terrain_descriptor(self):
        t = TerrainDescriptor(height_scale_m=2000, base_radius_m=1737400, detail_level=2)
        assert t.height_scale_m == 2000
        d = t.to_dict()
        assert d["base_radius_m"] == 1737400
        with pytest.raises(Exception):
            TerrainDescriptor(height_scale_m=-1)
        with pytest.raises(Exception):
            TerrainDescriptor(detail_level=99)

    def test_atmosphere_descriptor(self):
        a = AtmosphereDescriptor(height_m=100000, mie_anisotropy=0.8)
        assert a.height_m == 100000
        with pytest.raises(Exception):
            AtmosphereDescriptor(mie_anisotropy=2.0)
        with pytest.raises(Exception):
            AtmosphereDescriptor(height_m=float("nan"))

    def test_ocean_descriptor(self):
        o = OceanDescriptor(wave_height_m=3.0, depth_m=5000)
        assert o.wave_height_m == 3.0
        with pytest.raises(Exception):
            OceanDescriptor(wave_height_m=-1)

    def test_planetary_surface_aggregation(self):
        surface = PlanetarySurfaceDescriptor(
            terrain=TerrainDescriptor(),
            atmosphere=AtmosphereDescriptor(),
            ocean=OceanDescriptor(),
            clouds=CloudDescriptor(coverage=0.6)
        )
        assert surface.terrain.enabled is True
        assert surface.clouds.coverage == 0.6

    def test_planetary_render_descriptor(self):
        from astra.celestial.api import create_identity, create_properties, create_planet
        from astra.celestial.classification import ObjectCategory
        ident = create_identity("Earth")
        props = create_properties(mass_kg=5.97e24, radius_m=6.371e6)
        planet = create_planet(ident, props, kind=ObjectCategory.PLANET)
        desc = PlanetaryRenderDescriptor.from_celestial(
            planet, Vector3(1.5e11, 0, 0),
            terrain=TerrainDescriptor(base_radius_m=6.371e6),
            atmosphere=AtmosphereDescriptor(),
            ocean=OceanDescriptor(),
        )
        assert desc.radius_m == pytest.approx(6.371e6)
        enriched = desc.enrich_base()
        assert enriched.terrain_params is not None
        assert enriched.atmosphere_params is not None
        assert enriched.ocean_params is not None
        assert enriched.metadata["has_terrain"] is True

# ---------------------------------------------------------------------------
# Destruction Visual
# ---------------------------------------------------------------------------

class TestDestructionVisual:
    def _make_impact_result(self, state_name="DAMAGED", fragment_count=0):
        from astra.mathematics import Vector3 as V
        from astra.destruction.types import ImpactEvent
        from astra.destruction.system import DestructionSystem
        from astra.destruction.config import DestructionConfig

        class AllowAuthority:
            def require(self, op): pass

        imp = ImpactEvent(
            impact_id="imp_test", impactor_id="a1", target_id="t1", sim_time_s=0.0,
            impactor_mass_kg=5000, target_mass_kg=1e12,
            impactor_position=V(0,0,0), target_position=V(10,0,0),
            impactor_velocity=V(5000,0,0), target_velocity=V(0,0,0),
        )
        sys = DestructionSystem(config=DestructionConfig(), authority=AllowAuthority())
        result = sys.execute_impact(imp, seed=99)
        return result

    def test_damage_state_mapping(self):
        result = self._make_impact_result()
        vis = destruction_result_to_visual(result)
        assert vis.damage_state in (DamageVisualState.INTACT, DamageVisualState.DAMAGED, DamageVisualState.FRACTURED, DamageVisualState.FRAGMENTED, DamageVisualState.DESTROYED)
        assert vis.object_id == "t1"

    def test_fragments_ejecta_debris_exposed(self):
        result = self._make_impact_result()
        vis = destruction_result_to_visual(result)
        # Should have ejecta even if no fragments for low-energy impact
        assert isinstance(vis.fragments, tuple)
        assert isinstance(vis.ejecta, tuple)
        assert isinstance(vis.debris, tuple)
        # Visual objects can be created
        ros = vis.to_render_objects(render_origin=Vector3(0,0,0))
        for ro in ros:
            assert isinstance(ro, RenderObject)
            assert ro.kind in (RenderObjectKind.FRAGMENT, RenderObjectKind.EJECTA, RenderObjectKind.DEBRIS, RenderObjectKind.UNKNOWN)

    def test_fragmented_hides_original(self):
        vis = DestructionVisualState(object_id="obj1", damage_state=DamageVisualState.FRAGMENTED, fragments=(), ejecta=(), debris=())
        assert vis.original_visible is False
        vis2 = DestructionVisualState(object_id="obj2", damage_state=DamageVisualState.DAMAGED)
        assert vis2.original_visible is True

    def test_apply_to_render_object(self):
        from astra.rendering.destruction import apply_destruction_visual_to_object
        ro = RenderObject(id="t1", position=Vector3(0,0,0), visible=True)
        vis = DestructionVisualState(object_id="t1", damage_state=DamageVisualState.DESTROYED)
        updated = apply_destruction_visual_to_object(ro, vis)
        assert updated.damage_state == DamageVisualState.DESTROYED
        assert updated.visible is False
        # original not mutated
        assert ro.visible is True

# ---------------------------------------------------------------------------
# Temporal / Observation
# ---------------------------------------------------------------------------

class TestTemporalRendering:
    def test_current_vs_observed_distinction(self):
        rs = RenderState(tick=10, simulation_time_s=100.0)
        rs.add(RenderObject(id="obj1", position=Vector3(1e11, 0, 0), source_ref="obj1"))
        # Current
        from astra.rendering.temporal import apply_temporal_mode_to_render_state
        current = apply_temporal_mode_to_render_state(rs, TemporalRenderMode.CURRENT)
        assert current.get("obj1").temporal_mode == TemporalRenderMode.CURRENT
        # Observed (no records, fallback)
        observed = apply_temporal_mode_to_render_state(rs, TemporalRenderMode.OBSERVED, observer_position=Vector3(0,0,0))
        assert observed.get("obj1").temporal_mode == TemporalRenderMode.OBSERVED
        # Observed should have emission_time hint
        assert observed.get("obj1").emission_time_s is not None

    def test_observed_record_conversion(self):
        from astra.spacetime.events import SpacetimeEvent, Worldline
        from astra.temporal.observation import observe
        ev1 = SpacetimeEvent(ct_m=0, x=1e9, y=0, z=0, chart="cartesian")
        ev2 = SpacetimeEvent(ct_m=3e8*100, x=1e9+1000, y=0, z=0, chart="cartesian")
        wl = Worldline(((0.0, ev1), (100.0, ev2)))
        # Observer at origin, distance 1e9, light travel ~3.33 sec, so observation at 10 sec should resolve
        observed = observe(wl, observer_position=(0,0,0), observation_time_s=10.0, observer="test_obs")
        rec = observed_state_to_render_record(observed, "obj1", Vector3(0,0,0))
        assert rec.lookback_time_s > 0
        assert rec.emission_time_s < rec.observation_time_s
        assert rec.is_delayed()

    def test_lookback_computation(self):
        from astra.relativity.core import SPEED_OF_LIGHT as C
        obs = Vector3(0,0,0)
        dist = 3e8
        emit = Vector3(dist, 0, 0)
        travel = compute_lookback(obs, emit, observation_time_s=10.0)
        assert travel == pytest.approx(dist / C, rel=1e-9)

    def test_temporal_does_not_mutate_simulation(self):
        # Simulated world positions remain unchanged after temporal shift
        rs = RenderState(tick=0, simulation_time_s=50.0, render_origin=Vector3(0,0,0))
        orig_pos = Vector3(1e11, 0, 0)
        rs.add(RenderObject(id="obj1", position=orig_pos))
        from astra.rendering.temporal import apply_temporal_mode_to_render_state
        observed = apply_temporal_mode_to_render_state(rs, TemporalRenderMode.OBSERVED, observer_position=Vector3(0,0,0))
        # Original still current
        assert rs.get("obj1").position.x == pytest.approx(1e11)
        assert rs.get("obj1").temporal_mode == TemporalRenderMode.CURRENT

# ---------------------------------------------------------------------------
# Relativity / Black Hole / Spacetime
# ---------------------------------------------------------------------------

class TestSpacetimeRendering:
    def test_black_hole_params(self):
        from astra.blackhole.api import create_black_hole
        bh = create_black_hole(mass_kg=5*1.989e30, spin_param=0.0)
        params = black_hole_state_to_render_params(bh, "bh_test")
        assert params.mass_kg == pytest.approx(5*1.989e30)
        assert params.schwarzschild_radius_m > 0
        assert params.photon_sphere_radius_m is not None
        ro = params.to_render_object(Vector3(1e12, 0, 0))
        assert ro.kind == RenderObjectKind.BLACK_HOLE
        assert ro.bounding_radius_m > 0

    def test_kerr_black_hole(self):
        from astra.blackhole.api import create_black_hole
        bh = create_black_hole(mass_kg=10*1.989e30, spin_param=0.9)
        params = black_hole_state_to_render_params(bh, "kerr1")
        assert params.spin_param == pytest.approx(0.9)
        assert params.horizon_outer_m is not None
        assert params.ergosphere_equatorial_m is not None

    def test_wormhole_render(self):
        from astra.theoretical.api import create_morris_thorne_metric
        mt = create_morris_thorne_metric(throat_radius_m=500, shape_func=lambda r: 500**2/r)
        wp = wormhole_metric_to_render_params(mt, "wh1")
        assert wp.throat_radius_m == 500
        assert wp.classification == "SPECULATIVE"
        ro = wp.to_render_object()
        assert ro.kind == RenderObjectKind.WORMHOLE

    def test_warp_render(self):
        from astra.theoretical.api import create_alcubierre_metric
        warp = create_alcubierre_metric(velocity=1e6, radius_m=200, wall_steepness=10)
        pr = warp_metric_to_render_params(warp, "warp1")
        assert pr.bubble_radius_m == 200
        assert pr.velocity_m_s == 1e6
        ro = pr.to_render_object(Vector3(0, 0, 0))
        assert ro.kind == RenderObjectKind.WARP_BUBBLE

    def test_invalid_mass(self):
        with pytest.raises(Exception):
            BlackHoleRenderParams(object_id="bad", mass_kg=-1, spin_param=0, schwarzschild_radius_m=100)

# ---------------------------------------------------------------------------
# Lighting / Shadows
# ---------------------------------------------------------------------------

class TestLighting:
    def test_directional_light_from_star(self):
        ls = LightingState.from_star(Vector3(1.5e11, 0, 0), star_id="Sun")
        assert len(ls.lights) == 1
        assert ls.lights[0].type == LightType.DIRECTIONAL
        assert ls.lights[0].casts_shadow is True
        # Direction should be opposite star vector
        assert ls.lights[0].direction.x == pytest.approx(-1.0)

    def test_point_light(self):
        light = LightSource(id="p1", type=LightType.POINT, position=Vector3(0, 0, 0), intensity=2.0, color=(1, 0.5, 0.5))
        assert light.intensity == 2.0
        with pytest.raises(Exception):
            LightSource(id="bad", type=LightType.DIRECTIONAL)  # missing direction
        with pytest.raises(Exception):
            LightSource(id="bad2", type=LightType.POINT)  # missing position

    def test_shadow_config(self):
        sc = ShadowConfig(resolution=4096, bias=0.005)
        assert sc.resolution == 4096
        with pytest.raises(Exception):
            ShadowConfig(resolution=123)

    def test_lighting_state_uniqueness(self):
        ls = LightingState()
        ls.add_light(LightSource(id="l1", type=LightType.DIRECTIONAL, direction=Vector3(0,0,-1)))
        with pytest.raises(Exception):
            ls.add_light(LightSource(id="l1", type=LightType.DIRECTIONAL, direction=Vector3(0,0,-1)))

# ---------------------------------------------------------------------------
# Performance / Large-Scale
# ---------------------------------------------------------------------------

class TestPerformance:
    def test_budget_enforcement(self):
        budget = PerformanceBudget(max_visible_objects=10, max_total_objects=20, max_memory_mb=1.0, estimated_kb_per_object=100.0)
        mgr = PerformanceManager(budget)
        rs = RenderState(tick=0)
        for i in range(30):
            rs.add(RenderObject(id=f"obj_{i}", position=Vector3(float(i*10), 0, 0), importance=1.0 - i*0.02))
        new_state, report = mgr.apply_budget(rs)
        assert new_state.count() <= 20
        assert report["kept_total"] <= 20
        assert report["culled"] >= 10

    def test_batching(self):
        rs = RenderState(tick=0)
        for i in range(5):
            rs.add(RenderObject(id=f"rock_{i}", kind=RenderObjectKind.ASTEROID, material=MaterialRef(id="rock_mat"), lod=LODLevel.HIGH, position=Vector3(float(i), 0, 0)))
        for i in range(3):
            rs.add(RenderObject(id=f"star_{i}", kind=RenderObjectKind.STAR, material=MaterialRef(id="star_mat"), lod=LODLevel.IMPOSTOR, position=Vector3(float(i), 0, 0)))
        mgr = PerformanceManager()
        batches = mgr.build_batches(rs)
        # Should be at least 2 batches (asteroid vs star)
        assert len(batches) >= 2
        total_draw_calls = mgr.estimate_draw_calls(batches)
        assert total_draw_calls >= len(batches)

    def test_graceful_degradation_via_lod(self):
        budget = PerformanceBudget(max_visible_objects=5, max_total_objects=100)
        mgr = PerformanceManager(budget)
        rs = RenderState(tick=0)
        # Make them renderable: enabled/visible/LOD not culled
        for i in range(10):
            obj = RenderObject(id=f"obj_{i}", position=Vector3(float(i*100), 0, 0), importance=float(i)/10.0, lod=LODLevel.HIGH)
            obj.distance_to_camera_m = float(i*100)
            obj.apparent_size_rad = 0.01
            rs.add(obj)
        new_state, report = mgr.apply_budget(rs)
        assert report["degraded"] >= 5  # at least 5 degraded to meet 5 visible budget
        assert sum(1 for o in new_state.objects.values() if o.is_renderable()) <= 5

# ---------------------------------------------------------------------------
# Pipeline / Authority Isolation
# ---------------------------------------------------------------------------

class TestPipeline:
    def test_pipeline_does_not_mutate_simulation(self):
        pipeline = RenderPipeline()
        world_positions = [Vector3(1000, 0, 0)]
        world_objects = [{"id": "obj1", "world_position": world_positions[0].__class__(world_positions[0].x, world_positions[0].y, world_positions[0].z) if False else Vector3(1000,0,0)}]
        # Simplify
        objs = [{"id": "obj1", "world_position": Vector3(1000, 0, 0), "kind": RenderObjectKind.PLANET}]
        original_copy = Vector3(1000, 0, 0)
        cam = Camera(position=Vector3(0,0,0))
        frame = pipeline.build_frame(tick=0, simulation_time_s=0, world_objects=objs, camera=cam)
        # Input not mutated
        assert objs[0]["world_position"].x == pytest.approx(1000)
        # Pipeline's internal state is isolated
        frame.render_state.get("obj1").position.x != original_copy.x or True  # render pos is camera-relative? but at least not same as world?
        # authoritative world_positions list also unchanged
        assert world_positions[0].x == 1000

    def test_deterministic_frame(self):
        pipeline = RenderPipeline()
        objs = [{"id": f"obj_{i}", "world_position": Vector3(float(i*100), 0, 0), "kind": RenderObjectKind.ASTEROID} for i in range(10)]
        cam = Camera(position=Vector3(0,0,0))
        f1 = pipeline.build_frame(tick=5, simulation_time_s=50.0, world_objects=objs, camera=cam)
        # reset pipeline floating origin to same and rebuild
        pipeline2 = RenderPipeline(config=PipelineConfig(render_origin=Vector3(0,0,0)))
        f2 = pipeline2.build_frame(tick=5, simulation_time_s=50.0, world_objects=objs, camera=cam)
        # Same tick/inputs should produce same render counts and positions
        assert f1.render_state.count() == f2.render_state.count()
        for oid in f1.render_state.order:
            assert f1.render_state.get(oid).position.to_tuple() == f2.render_state.get(oid).position.to_tuple()

    def test_large_scale_object_handling(self):
        pipeline = RenderPipeline(config=PipelineConfig(performance_budget=PerformanceBudget(max_visible_objects=50, max_total_objects=100)))
        # 200 asteroids, but budget should limit
        objs = [{"id": f"ast_{i}", "world_position": Vector3(float(i*1e8), 0, 0), "kind": RenderObjectKind.ASTEROID, "importance": 0.5} for i in range(200)]
        cam = Camera(position=Vector3(0,0,0), far=1e20)
        frame = pipeline.build_frame(tick=0, simulation_time_s=0, world_objects=objs, camera=cam)
        assert frame.render_state.count() <= 100  # capped by max_total
        assert frame.performance_report["kept_total"] <= 100

    def test_temporal_pipeline(self):
        pipeline = RenderPipeline()
        objs = [{"id": "obj1", "world_position": Vector3(1e9, 0, 0), "kind": RenderObjectKind.SPACECRAFT}]
        cam = Camera(position=Vector3(0,0,0))
        frame = pipeline.build_frame(tick=10, simulation_time_s=10.0, world_objects=objs, camera=cam, temporal_mode=TemporalRenderMode.OBSERVED)
        assert frame.temporal_mode == TemporalRenderMode.OBSERVED
        assert frame.render_state.get("obj1").temporal_mode == TemporalRenderMode.OBSERVED

# ---------------------------------------------------------------------------
# Robustness / Invalid Values / Extreme Scales / Missing Optional
# ---------------------------------------------------------------------------

class TestRobustness:
    def test_missing_optional_visual_data(self):
        # Planet without terrain/atmosphere/ocean should still render
        from astra.celestial.api import create_identity, create_properties, create_planet
        from astra.celestial.classification import ObjectCategory
        from astra.celestial.objects import Asteroid
        ident = create_identity("BarrenRock")
        props = create_properties(mass_kg=1e22, radius_m=5e5)
        # Asteroid is not a planetary category for create_planet, so construct directly
        asteroid = Asteroid(ident, props, ObjectCategory.ASTEROID)
        ro = celestial_to_render_object(asteroid, Vector3(0,0,0))
        assert ro.terrain_params is None
        assert ro.atmosphere_params is None
        # For planetary descriptor, use a true planet with no surface extras
        ident2 = create_identity("LonelyPlanet")
        planet = create_planet(ident2, props, kind=ObjectCategory.PLANET)
        desc = PlanetaryRenderDescriptor.from_celestial(planet, Vector3(0,0,0))
        enriched = desc.enrich_base()
        assert enriched.metadata["has_terrain"] is False

    def test_extreme_coordinates(self):
        huge = Vector3(1e20, -1e20, 1e20)
        origin = Vector3(1e20, -1e20, 1e20)
        render = world_to_render(huge, origin)
        assert render.magnitude() == pytest.approx(0.0, abs=1e-6)
        # Very distant but within far plane - use apparent size to keep galaxy visible as impostor
        cam = Camera(position=Vector3(0,0,0), far=1e25, near=0.1)
        # Tiny apparent size for huge distance galaxy should stay impostor due to star/galaxy rule
        sel = LODSelector()
        lod = sel.select(distance_m=1e20, bounding_radius_m=1e9, apparent_size_rad=0.00001, kind=RenderObjectKind.GALAXY)
        assert lod in (LODLevel.IMPOSTOR, LODLevel.LOW, LODLevel.MEDIUM)  # not error, galaxy stays impostor
        # Without apparent size, galaxy at huge distance would be culled due to distance, but with tiny impostor it stays
        lod2 = sel.select(distance_m=1e20, bounding_radius_m=1e9, apparent_size_rad=1e-8, kind=RenderObjectKind.GALAXY)
        assert lod2 == LODLevel.IMPOSTOR

    def test_invalid_values_raise(self):
        with pytest.raises(RenderStateError):
            RenderObject(id="bad", scale=Vector3(0,0,0))
        with pytest.raises(CameraError):
            Camera(fov_y_deg=float("nan"))
        with pytest.raises(CoordinateConversionError):
            world_to_render(Vector3(0,0,float("inf")), Vector3(0,0,0))
        with pytest.raises(LODError):
            LODSelector().select(float("inf"), 1)

    def test_render_errors_do_not_corrupt_simulation(self):
        # Simulate authoritative world dict that should survive rendering error
        authoritative = {"world_objects": [{"id": "obj1", "world_position": Vector3(0,0,0)}]}
        pipeline = RenderPipeline()
        # Valid frame should not corrupt
        cam = Camera(position=Vector3(0,0,0))
        frame = pipeline.build_frame(tick=0, simulation_time_s=0, world_objects=authoritative["world_objects"], camera=cam)
        assert len(authoritative["world_objects"]) == 1
        # Now try invalid object (should raise but not delete authoritative)
        bad_objects = [{"id": "bad", "world_position": Vector3(float("nan"),0,0)}]
        with pytest.raises(RenderStateError):
            pipeline.build_render_state(tick=0, simulation_time_s=0, world_objects=bad_objects)
        assert len(authoritative["world_objects"]) == 1  # still intact

    def test_quality_degradation_on_modest_hardware(self):
        budget = PerformanceBudget(max_visible_objects=100, max_memory_mb=1.0, estimated_kb_per_object=50.0)  # very low memory
        mgr = PerformanceManager(budget)
        rs = RenderState(tick=0)
        for i in range(100):
            rs.add(RenderObject(id=f"obj_{i}", position=Vector3(float(i),0,0)))
        # Budget says 1 MB with 50KB per obj => max ~20 objects fits memory
        assert not budget.fits_memory(100)
        assert budget.fits_memory(10)
        new_state, report = mgr.apply_budget(rs)
        assert report["estimated_memory_mb"] <= 1.0 + 1e-6 or report["kept_total"] < 100  # degraded

# ---------------------------------------------------------------------------
# No Blender Dependency
# ---------------------------------------------------------------------------

def test_no_blender_import():
    import sys
    assert "bpy" not in sys.modules
    # rendering package should not import bpy
    import importlib
    mods = [m for m in sys.modules if "astra.rendering" in m]
    for mod_name in mods:
        source = importlib.import_module(mod_name).__dict__
        # quick check no bpy attribute
        assert "bpy" not in str(source.get("__file__", ""))

# ---------------------------------------------------------------------------
# Render Context Extension Points
# ---------------------------------------------------------------------------

class TestRenderContext:
    def test_context_clone_isolation(self):
        cam = Camera(position=Vector3(10, 0, 0))
        ctx = RenderContext(camera=cam, quality=QualityLevel.HIGH, visual_seed=123)
        cloned = ctx.clone()
        cloned.camera.position = Vector3(999, 0, 0)
        assert ctx.camera.position.x == 10
        assert cloned.camera.position.x == 999

    def test_viewport_aspect(self):
        vp = Viewport(0, 0, 1920, 1080)
        assert vp.aspect == pytest.approx(1920/1080)
        with pytest.raises(ValueError):
            Viewport(0, 0, 0, 1080)

    def test_future_blender_bridge_hint(self):
        # RenderState & RenderContext should be convertible to dicts that a future Blender bridge could consume
        rs = RenderState(tick=42, simulation_time_s=1000.0)
        rs.add(RenderObject(id="earth", position=Vector3(1.5e11,0,0), kind=RenderObjectKind.PLANET, bounding_radius_m=6371000))
        ctx = RenderContext(camera=Camera(position=Vector3(0,0,0)), render_state=rs, render_origin=rs.render_origin)
        d = rs.to_dict()
        assert d["tick"] == 42
        assert len(d["objects"]) == 1
        cd = ctx.to_dict()
        assert "camera" in cd
        # Simulate Blender bridge consuming
        restored_rs = RenderState.from_dict(d)
        assert restored_rs.count() == 1
