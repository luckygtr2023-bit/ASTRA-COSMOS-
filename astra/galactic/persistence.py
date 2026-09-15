"""Serialization — deterministic round-trip."""
from __future__ import annotations

from typing import Any, Dict, List

from .errors import GalacticValidationError
from .types import (
    CosmicWeb,
    Galaxy,
    GalaxyCluster,
    GalaxyGroup,
    HierarchyEdge,
    HierarchyRelation,
    Supercluster,
    CosmicVoid,
    Filament,
    Sheet,
    CosmicNode,
    Vec3,
    CoordinateContext,
    Frame,
    GalaxyType,
    Provenance,
)
from .provenance import ObservedValue, DerivedValue, SimulatedValue, UnknownValue


def _vec(v: Vec3) -> Dict[str, float]:
    return {"x": v.x, "y": v.y, "z": v.z}


def _vec_from(d: Dict[str, float]) -> Vec3:
    return Vec3(float(d["x"]), float(d["y"]), float(d["z"]))


def _ctx_to_dict(c: CoordinateContext) -> Dict[str, Any]:
    return {
        "frame": c.frame.value,
        "scale_factor": c.scale_factor,
        "epoch_gyr": c.epoch_gyr,
        "reference_object_id": c.reference_object_id,
    }


def _ctx_from_dict(d: Dict[str, Any]) -> CoordinateContext:
    return CoordinateContext(
        frame=Frame(d["frame"]),
        scale_factor=float(d["scale_factor"]),
        epoch_gyr=float(d["epoch_gyr"]),
        reference_object_id=d.get("reference_object_id"),
    )


def _value_to_dict(v: Any) -> Dict[str, Any]:
    if isinstance(v, ObservedValue):
        return {"kind": "ObservedValue", "value": v.value, "uncertainty": v.uncertainty, "unit": v.unit, "source": v.source, "provenance": v.provenance.value, "note": v.note}
    if isinstance(v, DerivedValue):
        return {"kind": "DerivedValue", "value": v.value, "unit": v.unit, "method": v.method, "inputs": list(v.inputs), "provenance": v.provenance.value}
    if isinstance(v, SimulatedValue):
        return {"kind": "SimulatedValue", "value": v.value, "unit": v.unit, "model": v.model, "seed": v.seed, "provenance": v.provenance.value}
    if isinstance(v, UnknownValue):
        return {"kind": "UnknownValue", "unit": v.unit, "reason": v.reason, "provenance": v.provenance.value}
    if v is None:
        return {"kind": "None"}
    raise GalacticValidationError(f"unknown AnyValue type {type(v)}")


def _value_from_dict(d: Dict[str, Any]) -> Any:
    kind = d.get("kind")
    if kind == "ObservedValue":
        return ObservedValue(value=float(d["value"]), uncertainty=float(d["uncertainty"]), unit=d["unit"], source=d["source"], provenance=Provenance(d["provenance"]), note=d.get("note"))
    if kind == "DerivedValue":
        return DerivedValue(value=float(d["value"]), unit=d["unit"], method=d["method"], inputs=tuple(d.get("inputs", ())), provenance=Provenance(d["provenance"]))
    if kind == "SimulatedValue":
        return SimulatedValue(value=float(d["value"]), unit=d["unit"], model=d["model"], seed=d.get("seed"), provenance=Provenance(d["provenance"]))
    if kind == "UnknownValue":
        return UnknownValue(unit=d["unit"], reason=d["reason"], provenance=Provenance(d["provenance"]))
    if kind == "None" or d is None:
        return None
    return None


def galaxy_to_dict(g: Galaxy) -> Dict[str, Any]:
    return {
        "galaxy_id": g.galaxy_id,
        "name": g.name,
        "galaxy_type": g.galaxy_type.value,
        "position": _vec(g.position),
        "coordinate_context": _ctx_to_dict(g.coordinate_context),
        "central_black_hole_ref": g.central_black_hole_ref,
        "provenance": g.provenance.value,
        "metadata": dict(g.metadata),
        "redshift": _value_to_dict(g.redshift) if g.redshift is not None else {"kind": "None"},
        "luminosity": _value_to_dict(g.luminosity) if g.luminosity is not None else {"kind": "None"},
    }


def galaxy_from_dict(d: Dict[str, Any]) -> Galaxy:
    # ctx required — if missing, use default comoving 1.0
    ctx = _ctx_from_dict(d["coordinate_context"]) if "coordinate_context" in d else CoordinateContext(frame=Frame.COMOVING, scale_factor=1.0, epoch_gyr=0.0)
    redshift = _value_from_dict(d["redshift"]) if "redshift" in d and d["redshift"] is not None else None
    luminosity = _value_from_dict(d["luminosity"]) if "luminosity" in d and d["luminosity"] is not None else None
    if isinstance(redshift, dict) and redshift.get("kind") == "None":
        redshift = None
    if isinstance(luminosity, dict) and luminosity.get("kind") == "None":
        luminosity = None
    return Galaxy(
        galaxy_id=d["galaxy_id"],
        name=d.get("name"),
        galaxy_type=GalaxyType(d["galaxy_type"]),
        position=_vec_from(d["position"]),
        coordinate_context=ctx,
        central_black_hole_ref=d.get("central_black_hole_ref"),
        provenance=Provenance(d.get("provenance", Provenance.SIMULATED_DATA.value)),
        metadata=dict(d.get("metadata", {})),
        redshift=redshift,
        luminosity=luminosity,
    )


def galaxy_group_to_dict(g: GalaxyGroup) -> Dict[str, Any]:
    return {
        "group_id": g.group_id,
        "member_galaxy_ids": list(g.member_galaxy_ids),
        "center": _vec(g.center),
        "coordinate_context": _ctx_to_dict(g.coordinate_context),
        "provenance": g.provenance.value,
        "metadata": dict(g.metadata),
    }


def galaxy_group_from_dict(d: Dict[str, Any]) -> GalaxyGroup:
    return GalaxyGroup(
        group_id=d["group_id"],
        member_galaxy_ids=tuple(d["member_galaxy_ids"]),
        center=_vec_from(d["center"]),
        coordinate_context=_ctx_from_dict(d["coordinate_context"]),
        provenance=Provenance(d.get("provenance", Provenance.SIMULATED_DATA.value)),
        metadata=dict(d.get("metadata", {})),
    )


def galaxy_cluster_to_dict(c: GalaxyCluster) -> Dict[str, Any]:
    return {
        "cluster_id": c.cluster_id,
        "member_group_ids": list(c.member_group_ids),
        "member_galaxy_ids": list(c.member_galaxy_ids),
        "center": _vec(c.center),
        "coordinate_context": _ctx_to_dict(c.coordinate_context),
        "provenance": c.provenance.value,
        "metadata": dict(c.metadata),
    }


def galaxy_cluster_from_dict(d: Dict[str, Any]) -> GalaxyCluster:
    return GalaxyCluster(
        cluster_id=d["cluster_id"],
        member_group_ids=tuple(d.get("member_group_ids", [])),
        member_galaxy_ids=tuple(d.get("member_galaxy_ids", [])),
        center=_vec_from(d["center"]),
        coordinate_context=_ctx_from_dict(d["coordinate_context"]),
        provenance=Provenance(d.get("provenance", Provenance.SIMULATED_DATA.value)),
        metadata=dict(d.get("metadata", {})),
    )


def supercluster_to_dict(s: Supercluster) -> Dict[str, Any]:
    return {
        "supercluster_id": s.supercluster_id,
        "member_cluster_ids": list(s.member_cluster_ids),
        "member_group_ids": list(s.member_group_ids),
        "member_galaxy_ids": list(s.member_galaxy_ids),
        "center": _vec(s.center),
        "coordinate_context": _ctx_to_dict(s.coordinate_context),
        "gravitationally_bound": s.gravitationally_bound,
        "provenance": s.provenance.value,
        "metadata": dict(s.metadata),
    }


def supercluster_from_dict(d: Dict[str, Any]) -> Supercluster:
    return Supercluster(
        supercluster_id=d["supercluster_id"],
        member_cluster_ids=tuple(d.get("member_cluster_ids", [])),
        member_group_ids=tuple(d.get("member_group_ids", [])),
        member_galaxy_ids=tuple(d.get("member_galaxy_ids", [])),
        center=_vec_from(d["center"]),
        coordinate_context=_ctx_from_dict(d["coordinate_context"]),
        gravitationally_bound=bool(d.get("gravitationally_bound", False)),
        provenance=Provenance(d.get("provenance", Provenance.SIMULATED_DATA.value)),
        metadata=dict(d.get("metadata", {})),
    )


def edge_to_dict(e: HierarchyEdge) -> Dict[str, str]:
    return {"parent_id": e.parent_id, "child_id": e.child_id, "relation": e.relation.value}


def edge_from_dict(d: Dict[str, str]) -> HierarchyEdge:
    return HierarchyEdge(d["parent_id"], d["child_id"], HierarchyRelation(d["relation"]))


def void_to_dict(v: CosmicVoid) -> Dict[str, Any]:
    return {
        "void_id": v.void_id,
        "center": _vec(v.center),
        "coordinate_context": _ctx_to_dict(v.coordinate_context),
        "characteristic_radius_mpc": _value_to_dict(v.characteristic_radius_mpc),
        "underdensity": _value_to_dict(v.underdensity),
        "boundary_kind": v.boundary_kind.value,
        "neighbor_structure_ids": list(v.neighbor_structure_ids),
        "provenance": v.provenance.value,
        "metadata": dict(v.metadata),
    }


def void_from_dict(d: Dict[str, Any]) -> CosmicVoid:
    from .types import VoidBoundaryKind
    return CosmicVoid(
        void_id=d["void_id"],
        center=_vec_from(d["center"]),
        coordinate_context=_ctx_from_dict(d["coordinate_context"]),
        characteristic_radius_mpc=_value_from_dict(d["characteristic_radius_mpc"]),
        underdensity=_value_from_dict(d["underdensity"]),
        boundary_kind=VoidBoundaryKind(d["boundary_kind"]),
        neighbor_structure_ids=tuple(d.get("neighbor_structure_ids", [])),
        provenance=Provenance(d.get("provenance", Provenance.SIMULATED_DATA.value)),
        metadata=dict(d.get("metadata", {})),
    )


def filament_to_dict(f: Filament) -> Dict[str, Any]:
    return {
        "filament_id": f.filament_id,
        "node_a_id": f.node_a_id,
        "node_b_id": f.node_b_id,
        "galaxy_ids": list(f.galaxy_ids),
        "group_ids": list(f.group_ids),
        "provenance": f.provenance.value,
        "metadata": dict(f.metadata),
    }


def filament_from_dict(d: Dict[str, Any]) -> Filament:
    return Filament(
        filament_id=d["filament_id"],
        node_a_id=d["node_a_id"],
        node_b_id=d["node_b_id"],
        galaxy_ids=tuple(d.get("galaxy_ids", [])),
        group_ids=tuple(d.get("group_ids", [])),
        provenance=Provenance(d.get("provenance", Provenance.SIMULATED_DATA.value)),
        metadata=dict(d.get("metadata", {})),
    )


def sheet_to_dict(s: Sheet) -> Dict[str, Any]:
    return {
        "sheet_id": s.sheet_id,
        "member_filament_ids": list(s.member_filament_ids),
        "provenance": s.provenance.value,
        "metadata": dict(s.metadata),
    }


def sheet_from_dict(d: Dict[str, Any]) -> Sheet:
    return Sheet(
        sheet_id=d["sheet_id"],
        member_filament_ids=tuple(d.get("member_filament_ids", [])),
        provenance=Provenance(d.get("provenance", Provenance.SIMULATED_DATA.value)),
        metadata=dict(d.get("metadata", {})),
    )


def node_to_dict(n: CosmicNode) -> Dict[str, Any]:
    return {
        "node_id": n.node_id,
        "center": _vec(n.center),
        "coordinate_context": _ctx_to_dict(n.coordinate_context),
        "host_cluster_id": n.host_cluster_id,
        "host_supercluster_id": n.host_supercluster_id,
        "provenance": n.provenance.value,
        "metadata": dict(n.metadata),
    }


def node_from_dict(d: Dict[str, Any]) -> CosmicNode:
    return CosmicNode(
        node_id=d["node_id"],
        center=_vec_from(d["center"]),
        coordinate_context=_ctx_from_dict(d["coordinate_context"]),
        host_cluster_id=d.get("host_cluster_id"),
        host_supercluster_id=d.get("host_supercluster_id"),
        provenance=Provenance(d.get("provenance", Provenance.SIMULATED_DATA.value)),
        metadata=dict(d.get("metadata", {})),
    )


def web_to_dict(w: CosmicWeb) -> Dict[str, Any]:
    return {
        "web_id": w.web_id,
        "node_ids": list(w.node_ids),
        "filament_ids": list(w.filament_ids),
        "sheet_ids": list(w.sheet_ids),
        "void_ids": list(w.void_ids),
        "provenance": w.provenance.value,
        "metadata": dict(w.metadata),
    }


def web_from_dict(d: Dict[str, Any]) -> CosmicWeb:
    return CosmicWeb(
        web_id=d["web_id"],
        node_ids=tuple(d.get("node_ids", [])),
        filament_ids=tuple(d.get("filament_ids", [])),
        sheet_ids=tuple(d.get("sheet_ids", [])),
        void_ids=tuple(d.get("void_ids", [])),
        provenance=Provenance(d.get("provenance", Provenance.SIMULATED_DATA.value)),
        metadata=dict(d.get("metadata", {})),
    )
