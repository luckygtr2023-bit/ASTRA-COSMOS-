"""Serialization for destruction results.

Deterministic round-trip: serialize -> deserialize -> serialize yields
identical, JSON-serialisable dicts. Replay-critical data (RNG seed used,
model version, provenance) is persisted. Geometry is RECOMPUTED from the
event on load (it is a deterministic function of event + config) and is
therefore not treated as canonical persisted state.
"""
from __future__ import annotations

from typing import Any, Dict

from astra.mathematics import Vector3

from .config import DestructionConfig
from .damage import DamageState
from .errors import PersistenceError
from .provenance import DataProvenance
from .types import (
    DebrisState,
    EjectaState,
    FragmentState,
    ImpactEnergy,
    ImpactEvent,
    ImpactMomentum,
    ImpactResult,
)


def _vec_to_dict(v: Vector3) -> Dict[str, float]:
    return {"x": v.x, "y": v.y, "z": v.z}


def _vec_from_dict(d: Dict[str, Any]) -> Vector3:
    return Vector3(float(d["x"]), float(d["y"]), float(d["z"]))


def event_to_dict(e: ImpactEvent) -> Dict[str, Any]:
    return {
        "impact_id": e.impact_id,
        "impactor_id": e.impactor_id,
        "target_id": e.target_id,
        "sim_time_s": e.sim_time_s,
        "impactor_mass_kg": e.impactor_mass_kg,
        "target_mass_kg": e.target_mass_kg,
        "impactor_position": _vec_to_dict(e.impactor_position),
        "target_position": _vec_to_dict(e.target_position),
        "impactor_velocity": _vec_to_dict(e.impactor_velocity),
        "target_velocity": _vec_to_dict(e.target_velocity),
        "impactor_radius_m": e.impactor_radius_m,
        "target_radius_m": e.target_radius_m,
        "reference_frame": e.reference_frame,
        "provenance": e.provenance.value,
        "metadata": dict(e.metadata),
    }


def event_from_dict(d: Dict[str, Any]) -> ImpactEvent:
    try:
        return ImpactEvent(
            impact_id=d["impact_id"],
            impactor_id=d["impactor_id"],
            target_id=d["target_id"],
            sim_time_s=float(d["sim_time_s"]),
            impactor_mass_kg=float(d["impactor_mass_kg"]),
            target_mass_kg=float(d["target_mass_kg"]),
            impactor_position=_vec_from_dict(d["impactor_position"]),
            target_position=_vec_from_dict(d["target_position"]),
            impactor_velocity=_vec_from_dict(d["impactor_velocity"]),
            target_velocity=_vec_from_dict(d["target_velocity"]),
            impactor_radius_m=float(d.get("impactor_radius_m", 0.0)),
            target_radius_m=float(d.get("target_radius_m", 0.0)),
            reference_frame=d.get("reference_frame", "world"),
            provenance=DataProvenance(d.get("provenance", DataProvenance.SIMULATED_DATA.value)),
            metadata=dict(d.get("metadata", {})),
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise PersistenceError(f"failed to deserialize ImpactEvent: {exc}") from exc


def fragment_to_dict(f: FragmentState) -> Dict[str, Any]:
    return {
        "fragment_id": f.fragment_id,
        "parent_id": f.parent_id,
        "impact_id": f.impact_id,
        "mass_kg": f.mass_kg,
        "position": _vec_to_dict(f.position),
        "velocity": _vec_to_dict(f.velocity),
        "created_at_s": f.created_at_s,
        "material": f.material,
        "provenance": f.provenance.value,
    }


def fragment_from_dict(d: Dict[str, Any]) -> FragmentState:
    return FragmentState(
        fragment_id=d["fragment_id"],
        parent_id=d["parent_id"],
        impact_id=d["impact_id"],
        mass_kg=float(d["mass_kg"]),
        position=_vec_from_dict(d["position"]),
        velocity=_vec_from_dict(d["velocity"]),
        created_at_s=float(d["created_at_s"]),
        material=d.get("material"),
        provenance=DataProvenance(d.get("provenance", DataProvenance.SIMULATED_DATA.value)),
    )


def ejecta_to_dict(p: EjectaState) -> Dict[str, Any]:
    return {
        "ejecta_id": p.ejecta_id,
        "impact_id": p.impact_id,
        "source_id": p.source_id,
        "mass_kg": p.mass_kg,
        "position": _vec_to_dict(p.position),
        "velocity": _vec_to_dict(p.velocity),
        "kinetic_energy_j": p.kinetic_energy_j,
        "created_at_s": p.created_at_s,
        "provenance": p.provenance.value,
    }


def ejecta_from_dict(d: Dict[str, Any]) -> EjectaState:
    return EjectaState(
        ejecta_id=d["ejecta_id"],
        impact_id=d["impact_id"],
        source_id=d["source_id"],
        mass_kg=float(d["mass_kg"]),
        position=_vec_from_dict(d["position"]),
        velocity=_vec_from_dict(d["velocity"]),
        kinetic_energy_j=float(d["kinetic_energy_j"]),
        created_at_s=float(d["created_at_s"]),
        provenance=DataProvenance(d.get("provenance", DataProvenance.SIMULATED_DATA.value)),
    )


def debris_to_dict(d0: DebrisState) -> Dict[str, Any]:
    return {
        "debris_id": d0.debris_id,
        "origin_impact_id": d0.origin_impact_id,
        "mass_kg": d0.mass_kg,
        "position": _vec_to_dict(d0.position),
        "velocity": _vec_to_dict(d0.velocity),
        "created_at_s": d0.created_at_s,
        "is_ejecta": d0.is_ejecta,
        "provenance": d0.provenance.value,
    }


def debris_from_dict(d: Dict[str, Any]) -> DebrisState:
    return DebrisState(
        debris_id=d["debris_id"],
        origin_impact_id=d["origin_impact_id"],
        mass_kg=float(d["mass_kg"]),
        position=_vec_from_dict(d["position"]),
        velocity=_vec_from_dict(d["velocity"]),
        created_at_s=float(d["created_at_s"]),
        is_ejecta=bool(d.get("is_ejecta", False)),
        provenance=DataProvenance(d.get("provenance", DataProvenance.SIMULATED_DATA.value)),
    )


def result_to_dict(r: ImpactResult) -> Dict[str, Any]:
    return {
        "event": event_to_dict(r.event),
        "target_state_before": r.target_state_before.value,
        "target_state_after": r.target_state_after.value,
        "rng_seed_used": r.rng_seed_used,
        "model_version": r.model_version,
        "provenance": r.provenance.value,
        "fragments": [fragment_to_dict(f) for f in r.fragments],
        "ejecta": [ejecta_to_dict(p) for p in r.ejecta],
        "debris": [debris_to_dict(d0) for d0 in r.debris],
        "energy": {
            "kinetic_energy_j": r.energy.kinetic_energy_j,
            "deposited_energy_j": r.energy.deposited_energy_j,
            "fragmentation_energy_j": r.energy.fragmentation_energy_j,
            "thermal_energy_j": r.energy.thermal_energy_j,
            "residual_kinetic_energy_j": r.energy.residual_kinetic_energy_j,
        },
        "momentum": {
            "relative": _vec_to_dict(r.momentum.relative_momentum_kg_m_s),
            "transferred": _vec_to_dict(r.momentum.transferred_momentum_kg_m_s),
            "residual": _vec_to_dict(r.momentum.residual_momentum_kg_m_s),
        },
    }


def result_from_dict(d: Dict[str, Any], *, config: DestructionConfig | None = None) -> ImpactResult:
    try:
        event = event_from_dict(d["event"])
        before = DamageState(d["target_state_before"])
        after = DamageState(d["target_state_after"])
        fragments = tuple(fragment_from_dict(f) for f in d.get("fragments", []))
        ejecta = tuple(ejecta_from_dict(p) for p in d.get("ejecta", []))
        debris = tuple(debris_from_dict(d0) for d0 in d.get("debris", []))
        e = d["energy"]
        energy = ImpactEnergy(
            kinetic_energy_j=float(e["kinetic_energy_j"]),
            deposited_energy_j=float(e["deposited_energy_j"]),
            fragmentation_energy_j=float(e["fragmentation_energy_j"]),
            thermal_energy_j=float(e["thermal_energy_j"]),
            residual_kinetic_energy_j=float(e["residual_kinetic_energy_j"]),
        )
        m = d["momentum"]
        momentum = ImpactMomentum(
            relative_momentum_kg_m_s=_vec_from_dict(m["relative"]),
            transferred_momentum_kg_m_s=_vec_from_dict(m["transferred"]),
            residual_momentum_kg_m_s=_vec_from_dict(m["residual"]),
        )
        # Geometry is a deterministic function of event + config: recomputed.
        from .geometry import compute_impact_geometry

        geom = compute_impact_geometry(event, config if config is not None else DestructionConfig())
        return ImpactResult(
            event=event,
            geometry=geom,
            energy=energy,
            momentum=momentum,
            target_state_before=before,
            target_state_after=after,
            fragments=fragments,
            ejecta=ejecta,
            debris=debris,
            rng_seed_used=int(d.get("rng_seed_used", 0)),
            model_version=d.get("model_version", "astra.destruction.v1"),
            provenance=DataProvenance(d.get("provenance", DataProvenance.SIMULATED_DATA.value)),
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise PersistenceError(f"failed to deserialize ImpactResult: {exc}") from exc


def damage_ledger_to_dict(ledger: Dict[str, DamageState]) -> Dict[str, str]:
    return {k: v.value for k, v in ledger.items()}


def damage_ledger_from_dict(d: Dict[str, str]) -> Dict[str, DamageState]:
    try:
        return {k: DamageState(v) for k, v in d.items()}
    except ValueError as exc:
        raise PersistenceError(f"failed to deserialize damage ledger: {exc}") from exc
