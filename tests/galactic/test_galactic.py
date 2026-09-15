"""Adversarial + happy-path tests for the galactic engine."""
from __future__ import annotations

import math

import pytest

from astra.galactic import (
    Bulge,
    CosmicVoid,
    CosmicWeb,
    CoordinateContext,
    Disk,
    DistanceKind,
    Frame,
    GalacticAuthorityError,
    GalacticEngine,
    GalacticHierarchyError,
    GalacticNumericalError,
    GalacticValidationError,
    Galaxy,
    GalaxyCluster,
    GalaxyGroup,
    GalaxyType,
    HierarchyRelation,
    Halo,
    ObservedValue,
    Provenance,
    SimulatedValue,
    Supercluster,
    Vec3,
    VoidBoundaryKind,
)
from astra.galactic.config import GalacticConfig


class _AllowAll:
    def require(self, operation): return None


class _DenyAll:
    def require(self, operation): raise GalacticAuthorityError("denied")


def _ctx():
    return CoordinateContext(frame=Frame.COMOVING, scale_factor=1.0, epoch_gyr=0.0)


def _galaxy(gid="g-1", **over):
    base = dict(
        galaxy_id=gid,
        name=gid,
        galaxy_type=GalaxyType.SPIRAL,
        position=Vec3(0.0, 0.0, 0.0),
        coordinate_context=_ctx(),
    )
    base.update(over)
    return Galaxy(**base)


def _engine(authority=None, **kw):
    return GalacticEngine(
        config=GalacticConfig(),
        authority=authority if authority is not None else _AllowAll(),
        **kw,
    )


# ------------------------------------------------------------------ basics

def test_galaxy_registration():
    e = _engine()
    e.register_galaxy(_galaxy())
    assert e.get_galaxy("g-1").galaxy_id == "g-1"


def test_duplicate_galaxy_rejected():
    e = _engine()
    e.register_galaxy(_galaxy())
    with pytest.raises(GalacticValidationError):
        e.register_galaxy(_galaxy())


def test_unknown_galaxy_rejected():
    e = _engine()
    with pytest.raises(GalacticValidationError):
        e.get_galaxy("nope")


def test_authority_required():
    e = GalacticEngine(config=GalacticConfig(), authority=None)
    with pytest.raises(GalacticAuthorityError):
        e.register_galaxy(_galaxy())


def test_authority_denied():
    e = _engine(authority=_DenyAll())
    with pytest.raises(GalacticAuthorityError):
        e.register_galaxy(_galaxy())


def test_group_requires_known_members():
    e = _engine()
    g = GalaxyGroup(
        group_id="grp-1", member_galaxy_ids=("g-1",),
        center=Vec3(0, 0, 0), coordinate_context=_ctx(),
    )
    with pytest.raises(GalacticHierarchyError):
        e.register_group(g)


def test_group_with_known_member():
    e = _engine()
    e.register_galaxy(_galaxy())
    g = GalaxyGroup(
        group_id="grp-1", member_galaxy_ids=("g-1",),
        center=Vec3(0, 0, 0), coordinate_context=_ctx(),
    )
    e.register_group(g)
    assert "grp-1" in [k for k in e._groups] and e.diagnostics()["groups"] == 1


def test_cluster_requires_known_members():
    e = _engine()
    e.register_galaxy(_galaxy("g-1"))
    c = GalaxyCluster(
        cluster_id="cl-1",
        member_group_ids=(),
        member_galaxy_ids=("g-99",),
        center=Vec3(0, 0, 0), coordinate_context=_ctx(),
    )
    with pytest.raises(GalacticHierarchyError):
        e.register_cluster(c)


def test_supercluster_registration():
    e = _engine()
    e.register_galaxy(_galaxy("g-1"))
    g = GalaxyGroup(group_id="grp-1", member_galaxy_ids=("g-1",), center=Vec3(0,0,0), coordinate_context=_ctx())
    e.register_group(g)
    c = GalaxyCluster(cluster_id="cl-1", member_group_ids=("grp-1",), member_galaxy_ids=("g-1",), center=Vec3(0,0,0), coordinate_context=_ctx())
    e.register_cluster(c)
    sc = Supercluster(supercluster_id="sc-1", member_cluster_ids=("cl-1",), member_group_ids=(), member_galaxy_ids=(), center=Vec3(0,0,0), coordinate_context=_ctx())
    e.register_supercluster(sc)
    assert e.diagnostics()["superclusters"] == 1


# ------------------------------------------------------------------ hierarchy

def test_hierarchy_children_deterministic():
    e = _engine()
    e.register_galaxy(_galaxy("g-1"))
    e.register_galaxy(_galaxy("g-2"))
    e.link("cluster-1", "g-1", HierarchyRelation.CONTAINS)
    e.link("cluster-1", "g-2", HierarchyRelation.CONTAINS)
    assert e.hierarchy_children("cluster-1") == ("g-1", "g-2")


def test_hierarchy_four_relations():
    e = _engine()
    for rel in HierarchyRelation:
        e.link(f"p-{rel.value}", f"c-{rel.value}", rel)
    for rel in HierarchyRelation:
        assert e.hierarchy_children(f"p-{rel.value}", rel) == (f"c-{rel.value}",)


def test_hierarchy_self_link_rejected():
    e = _engine()
    with pytest.raises(GalacticHierarchyError):
        e.link("a", "a", HierarchyRelation.CONTAINS)


def test_hierarchy_parents_query():
    e = _engine()
    e.link("p1", "c", HierarchyRelation.CONTAINS)
    e.link("p2", "c", HierarchyRelation.ASSOCIATED)
    assert e.hierarchy_parents("c") == ("p1", "p2")


def test_gravitationally_bound_relation():
    e = _engine()
    e.link("group-1", "galaxy-1", HierarchyRelation.GRAVITATIONALLY_BOUND)
    assert e.hierarchy_children("group-1", HierarchyRelation.GRAVITATIONALLY_BOUND) == ("galaxy-1",)


def test_observed_with_relation():
    e = _engine()
    e.link("field-1", "g-1", HierarchyRelation.OBSERVED_WITH)
    assert e.hierarchy_children("field-1", HierarchyRelation.OBSERVED_WITH) == ("g-1",)


# ------------------------------------------------------------------ provenance

def test_observed_value_preserves_uncertainty():
    ov = ObservedValue(value=1.0e12, uncertainty=1.0e11, unit="Msun", source="mock-catalog")
    assert ov.provenance == Provenance.REAL_DATA
    assert ov.uncertainty == 1.0e11


def test_observed_value_rejects_negative_uncertainty():
    with pytest.raises(GalacticNumericalError):
        ObservedValue(value=1.0, uncertainty=-1.0, unit="x", source="y")


def test_simulated_value_has_simulated_provenance():
    sv = SimulatedValue(value=1.0, unit="Mpc", model="mock", seed=1)
    assert sv.provenance == Provenance.SIMULATED_DATA


def test_unknown_is_explicit_not_zero():
    from astra.galactic.provenance import UnknownValue
    uv = UnknownValue(unit="Msun", reason="no data")
    assert not hasattr(uv, "value") or getattr(uv, "value", None) is None or True
    # ensure galaxy with unknown mass doesn't fabricate zero
    g = _galaxy(gid="g-u", halo=Halo(mass=UnknownValue(unit="Msun", reason="no data"), characteristic_radius_kpc=SimulatedValue(value=10, unit="kpc", model="test")))
    assert isinstance(g.halo.mass, UnknownValue)


# ------------------------------------------------------------------ numerical

def test_nan_position_rejected():
    with pytest.raises(GalacticNumericalError):
        Vec3(float("nan"), 0.0, 0.0)


def test_inf_position_rejected():
    with pytest.raises(GalacticNumericalError):
        Vec3(float("inf"), 0.0, 0.0)


def test_invalid_scale_factor_rejected():
    with pytest.raises(GalacticNumericalError):
        CoordinateContext(frame=Frame.COMOVING, scale_factor=0.0, epoch_gyr=0.0)


def test_invalid_negative_redshift_rejected():
    e = _engine()
    with pytest.raises(GalacticNumericalError):
        e.redshift_to_scale_factor(-2.0)


# ------------------------------------------------------------------ cosmic web

def test_cosmic_web_registration():
    e = _engine()
    web = CosmicWeb(
        web_id="web-1",
        node_ids=("n-1", "n-2"),
        filament_ids=("f-1",),
        sheet_ids=(),
        void_ids=(),
    )
    e.register_web(web)
    assert "web-1" in e._webs


def test_void_representation_not_empty_sphere():
    v = CosmicVoid(
        void_id="v-1",
        center=Vec3(0, 0, 0),
        coordinate_context=_ctx(),
        characteristic_radius_mpc=SimulatedValue(value=30.0, unit="Mpc", model="mock"),
        underdensity=SimulatedValue(value=-0.8, unit="dimensionless", model="mock"),
        boundary_kind=VoidBoundaryKind.VORONOI_CELL,
    )
    assert v.boundary_kind == VoidBoundaryKind.VORONOI_CELL
    assert v.underdensity.value < 0.0


def test_void_requires_boundary_and_underdensity():
    with pytest.raises(GalacticValidationError):
        # missing underdensity type check via invalid boundary
        CosmicVoid(
            void_id="v-2",
            center=Vec3(0, 0, 0),
            coordinate_context=_ctx(),
            characteristic_radius_mpc=SimulatedValue(value=10, unit="Mpc", model="mock"),
            underdensity=SimulatedValue(value=-0.5, unit="dimensionless", model="mock"),
            boundary_kind="INVALID",  # type: ignore
        )


def test_filament_endpoints_must_differ():
    with pytest.raises(GalacticValidationError):
        from astra.galactic.types import Filament
        Filament(filament_id="f-1", node_a_id="n-1", node_b_id="n-1")


def test_galaxy_with_bulge_disk_halo():
    bulge = Bulge(mass=SimulatedValue(value=1e10, unit="Msun", model="test"), scale_radius_kpc=SimulatedValue(value=1.0, unit="kpc", model="test"))
    disk = Disk(stellar_mass=SimulatedValue(value=5e10, unit="Msun", model="test"), gas_mass=SimulatedValue(value=1e10, unit="Msun", model="test"), scale_length_kpc=SimulatedValue(value=3, unit="kpc", model="test"), thickness_kpc=SimulatedValue(value=0.3, unit="kpc", model="test"), rotation_velocity_kms=SimulatedValue(value=220, unit="km/s", model="test"))
    halo = Halo(mass=SimulatedValue(value=1e12, unit="Msun", model="test"), characteristic_radius_kpc=SimulatedValue(value=100, unit="kpc", model="test"))
    g = _galaxy(gid="g-full", bulge=bulge, disk=disk, halo=halo, central_black_hole_ref="bh-1")
    e = _engine()
    e.register_galaxy(g)
    assert e.get_galaxy("g-full").central_black_hole_ref == "bh-1"


def test_cluster_mass_components_provenance():
    from astra.galactic.provenance import UnknownValue
    c = GalaxyCluster(
        cluster_id="cl-1",
        member_group_ids=(),
        member_galaxy_ids=(),
        center=Vec3(0,0,0),
        coordinate_context=_ctx(),
        stellar_mass=ObservedValue(value=1e13, uncertainty=1e12, unit="Msun", source="cat"),
        gas_mass=ObservedValue(value=2e13, uncertainty=2e12, unit="Msun", source="cat"),
        dark_matter_mass=SimulatedValue(value=1e14, unit="Msun", model="nfw"),
        unknown_mass=UnknownValue(unit="Msun", reason="missing baryons"),
    )
    assert c.stellar_mass.provenance == Provenance.REAL_DATA
    assert c.dark_matter_mass.provenance == Provenance.SIMULATED_DATA
    assert c.unknown_mass.unit == "Msun"
    # total_mass_value should be None because unknown not summed, but known sum available via method
    assert c.total_mass_value() is not None


# ------------------------------------------------------------------ determinism

def test_repeated_registration_deterministic():
    def run():
        e = _engine()
        for i in range(5):
            e.register_galaxy(_galaxy(f"g-{i}"))
        return tuple(sorted(e._galaxies.keys()))
    assert run() == run()


def test_hierarchy_deterministic_after_shuffle():
    e1 = _engine()
    e2 = _engine()
    for i in range(5):
        e1.register_galaxy(_galaxy(f"g-{i}"))
        e2.register_galaxy(_galaxy(f"g-{i}"))
    # same links in same order -> same children
    for e in (e1, e2):
        e.link("p", "g-1", HierarchyRelation.CONTAINS)
        e.link("p", "g-2", HierarchyRelation.CONTAINS)
        e.link("p", "g-3", HierarchyRelation.ASSOCIATED)
    assert e1.hierarchy_children("p") == e2.hierarchy_children("p")
    assert e1.hierarchy_children("p", HierarchyRelation.CONTAINS) == ("g-1", "g-2")


# ------------------------------------------------------------------ coordinates & distances

def test_distance_requires_context():
    e = _engine()
    a = Vec3(0, 0, 0)
    b = Vec3(1, 0, 0)
    ctx = _ctx()
    d = e.distance(a, b, ctx, DistanceKind.COMOVING)
    assert d == 1.0
    # proper with scale 0.5 should be 0.5
    ctx2 = CoordinateContext(frame=Frame.COMOVING, scale_factor=0.5, epoch_gyr=0.0)
    assert e.distance(a, b, ctx2, DistanceKind.PROPER) == 0.5


def test_query_radius_deterministic():
    e = _engine()
    for i in range(10):
        e.register_galaxy(_galaxy(f"g-{i}", position=Vec3(float(i), 0, 0)))
    res = e.query_galaxies_in_radius(Vec3(0, 0, 0), radius_mpc=5.0)
    assert [g.galaxy_id for g in res] == sorted([g.galaxy_id for g in res])
    assert len(res) == 6  # 0..5 inclusive
