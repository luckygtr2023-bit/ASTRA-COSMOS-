"""Adversarial tests for astra.destruction: invalid inputs, limits,
authority, atomicity, corrupt persistence, and determinism audits.
"""
from __future__ import annotations

import json
import math
import pathlib

import pytest

from astra.destruction import (
    AuthorityError,
    DamageState,
    DestructionConfig,
    DestructionSystem,
    ImpactEvent,
    ImpactValidationError,
    LimitExceededError,
    LimitsConfig,
    NumericalError,
    PersistenceError,
    Vec3,
    transition,
)
from astra.destruction.persistence import (
    damage_ledger_from_dict,
    result_from_dict,
    result_to_dict,
)
from astra.destruction.validation import require_positive


class _AllowAll:
    def require(self, operation: str) -> None:
        return None


class _DenyAll:
    def require(self, operation: str) -> None:
        raise AuthorityError(f"denied: {operation}", operation=operation)


class _ExplodingEntities:
    """Registrar that fails mid-registration (atomicity probe)."""

    def register(self, entity_id, kind, payload):
        raise RuntimeError("registrar exploded")

    def unregister(self, entity_id):
        return None

    def exists(self, entity_id):
        return False


def _make_event(**over):
    base = dict(
        impact_id="imp-1",
        impactor_id="ast-1",
        target_id="earth",
        sim_time_s=100.0,
        impactor_mass_kg=1.0e15,
        target_mass_kg=5.972e24,
        impactor_position=Vec3(6.371e6 + 1.0e5, 0.0, 0.0),
        target_position=Vec3(0.0, 0.0, 0.0),
        impactor_velocity=Vec3(-2.0e4, 0.0, 0.0),
        target_velocity=Vec3(0.0, 0.0, 0.0),
        impactor_radius_m=1.0e3,
        target_radius_m=6.371e6,
    )
    base.update(over)
    return ImpactEvent(**base)


def _sys(**kw):
    return DestructionSystem(
        config=kw.pop("config", DestructionConfig()),
        authority=kw.pop("authority", _AllowAll()),
        **kw,
    )


# --------------------------------------------------------- invalid inputs


def test_zero_relative_velocity_rejected():
    s = _sys()
    ev = _make_event(impactor_velocity=Vec3(0.0, 0.0, 0.0))
    with pytest.raises(ImpactValidationError):
        s.execute_impact(ev, seed=4)


def test_below_minimum_relative_speed_rejected():
    s = _sys()
    ev = _make_event(impactor_velocity=Vec3(-1.0e-4, 0.0, 0.0))
    with pytest.raises(ImpactValidationError):
        s.execute_impact(ev, seed=4)


def test_extreme_velocity_accepted():
    s = _sys()
    # 0.67c relative: Newtonian model must still be numerically stable.
    # specific energy = 0.25*v^2 rel <=> ~1.7e6 J/kg here -> FRAGMENTED.
    ev = _make_event(impactor_velocity=Vec3(-2.0e8, 0.0, 0.0))
    r = s.execute_impact(ev, seed=5)
    assert r.energy.kinetic_energy_j > 0
    assert math.isfinite(r.energy.kinetic_energy_j)
    assert r.target_state_after == DamageState.FRAGMENTED


def test_extreme_mass_and_velocity_drives_destroyed():
    s = _sys()
    ev = _make_event(
        impactor_mass_kg=1.0e24, impactor_velocity=Vec3(-2.0e8, 0.0, 0.0)
    )
    r = s.execute_impact(ev, seed=6)
    assert r.target_state_after == DamageState.DESTROYED


def test_nan_velocity_rejected_at_event_construction():
    with pytest.raises(NumericalError):
        _make_event(impactor_velocity=Vec3(float("nan"), 0.0, 0.0))


def test_inf_position_rejected_at_event_construction():
    with pytest.raises(NumericalError):
        _make_event(target_position=Vec3(float("inf"), 0.0, 0.0))


def test_negative_mass_rejected():
    with pytest.raises(NumericalError):
        require_positive("mass", -1.0)
    s = _sys()
    with pytest.raises(NumericalError):
        s.execute_impact(_make_event(impactor_mass_kg=-10.0), seed=1)


def test_zero_mass_rejected():
    with pytest.raises(NumericalError):
        require_positive("mass", 0.0)
    s = _sys()
    with pytest.raises(NumericalError):
        s.execute_impact(_make_event(target_mass_kg=0.0), seed=1)


def test_bool_mass_rejected():
    with pytest.raises(NumericalError):
        _make_event(impactor_mass_kg=True)


def test_negative_radius_rejected():
    with pytest.raises(NumericalError):
        _make_event(target_radius_m=-1.0)


def test_same_impactor_and_target_rejected():
    s = _sys()
    with pytest.raises(ImpactValidationError):
        s.execute_impact(_make_event(impactor_id="earth"), seed=1)


def test_empty_impact_id_rejected():
    s = _sys()
    with pytest.raises(ImpactValidationError):
        s.execute_impact(_make_event(impact_id=""), seed=1)


def test_non_int_recursion_depth_rejected():
    s = _sys()
    with pytest.raises(NumericalError):
        s.execute_impact(_make_event(), seed=1, recursion_depth=1.5)  # type: ignore[arg-type]


# ---------------------------------------------------------------- limits


def test_min_impact_energy_floor():
    cfg = DestructionConfig(limits=LimitsConfig(min_impact_energy_j=1e40))
    s = _sys(config=cfg)
    with pytest.raises(LimitExceededError):
        s.execute_impact(_make_event(), seed=13)


def test_fragment_count_limit_enforced():
    cfg = DestructionConfig(limits=LimitsConfig(max_fragments_per_impact=1))
    s = _sys(config=cfg)
    ev = _make_event(impactor_mass_kg=1e24, impactor_velocity=Vec3(-1e6, 0, 0))
    with pytest.raises(LimitExceededError):
        s.execute_impact(ev, seed=12)


def test_recursion_depth_limit_enforced():
    s = _sys()
    with pytest.raises(LimitExceededError):
        s.execute_impact(_make_event(), seed=1, recursion_depth=99)


def test_ejecta_limit_zero_disables_ejecta_without_crash():
    cfg = DestructionConfig(limits=LimitsConfig(max_ejecta_per_impact=0))
    s = _sys(config=cfg)
    r = s.execute_impact(_make_event(), seed=1)
    assert r.ejecta == ()
    assert all(not d.is_ejecta for d in r.debris)


def test_invalid_config_values_rejected():
    with pytest.raises(ValueError):
        DestructionConfig(fragmentation_energy_fraction=0.6, thermal_energy_fraction=0.6)
    with pytest.raises(ValueError):
        DestructionConfig(momentum_transfer_efficiency=1.5)
    with pytest.raises(ValueError):
        DestructionConfig(limits=LimitsConfig(max_fragments_per_impact=-1))
    with pytest.raises(ValueError):
        DestructionConfig(grazing_sin_threshold=2.0)


# -------------------------------------------------------------- authority


def test_authority_required_when_unconfigured():
    s = DestructionSystem(config=DestructionConfig(), authority=None)
    with pytest.raises(AuthorityError):
        s.execute_impact(_make_event(), seed=8)
    with pytest.raises(AuthorityError):
        s.set_damage_state("earth", DamageState.DAMAGED)
    # Secondary scans are authority-gated even with a valid parent result.
    parent = _sys().execute_impact(_make_event(impactor_mass_kg=1e22), seed=8)
    with pytest.raises(AuthorityError):
        s.execute_secondary_impacts(parent, targets=[], seed=8)


def test_authority_denied_by_provider():
    s = _sys(authority=_DenyAll())
    with pytest.raises(AuthorityError):
        s.execute_impact(_make_event(), seed=9)


def test_destruction_authority_error_is_core_compatible():
    from astra.core.exceptions import AuthorityError as CoreAuthorityError

    s = DestructionSystem(config=DestructionConfig(), authority=None)
    with pytest.raises(CoreAuthorityError):
        s.execute_impact(_make_event(), seed=8)


# -------------------------------------------------------------- atomicity


def test_failed_impact_leaves_damage_ledger_untouched():
    s = _sys(entities=_ExplodingEntities())
    ev = _make_event(impactor_mass_kg=1e22)
    with pytest.raises(RuntimeError):
        s.execute_impact(ev, seed=30)
    assert s.get_damage_state("earth") == DamageState.INTACT
    assert s.diagnostics()["impacts_executed"] == 0


def test_failed_impact_preserves_prior_damage_state():
    s = _sys()
    s.set_damage_state("earth", DamageState.FRACTURED)
    s2_entities = _ExplodingEntities()
    s.entities = s2_entities
    ev = _make_event(impactor_mass_kg=1e24, impactor_velocity=Vec3(-1e6, 0, 0))
    with pytest.raises(RuntimeError):
        s.execute_impact(ev, seed=31)
    assert s.get_damage_state("earth") == DamageState.FRACTURED


# ------------------------------------------------------------ persistence


def test_corrupt_result_payload_rejected():
    s = _sys()
    r = s.execute_impact(_make_event(impactor_mass_kg=1e22), seed=32)
    d = result_to_dict(r)
    corrupt = dict(d)
    del corrupt["event"]["impact_id"]
    with pytest.raises(PersistenceError):
        result_from_dict(corrupt)
    corrupt2 = dict(d)
    corrupt2["target_state_after"] = "MOLTEN"  # not a DamageState
    with pytest.raises(PersistenceError):
        result_from_dict(corrupt2)


def test_persistence_error_is_core_compatible():
    from astra.core.exceptions import PersistenceError as CorePersistenceError

    with pytest.raises(CorePersistenceError):
        result_from_dict({"event": {}})


def test_corrupt_damage_ledger_rejected():
    with pytest.raises(PersistenceError):
        damage_ledger_from_dict({"earth": "SLIGHTLY_SINGED"})


def test_result_roundtrip_through_json_pipeline():
    s = _sys()
    r = s.execute_impact(_make_event(impactor_mass_kg=1e22), seed=33)
    payload = result_to_dict(r)
    for _ in range(2):  # repeated round trips are stable
        payload = result_to_dict(result_from_dict(json.loads(json.dumps(payload))))
    r2 = result_from_dict(payload)
    assert r2.rng_seed_used == 33
    assert r2.model_version == "astra.destruction.v1"
    assert len(r2.fragments) == len(r.fragments)


# ------------------------------------------------------------- state rules


def test_backward_transition_raises():
    with pytest.raises(ImpactValidationError):
        transition(DamageState.DESTROYED, DamageState.INTACT)
    with pytest.raises(ImpactValidationError):
        transition(DamageState.FRAGMENTED, DamageState.DAMAGED)


def test_set_damage_state_type_checked():
    s = _sys()
    with pytest.raises(ImpactValidationError):
        s.set_damage_state("earth", "BROKEN")


# ----------------------------------------------------- determinism audits


def test_no_global_rng_wallclock_or_uuid_in_package():
    import astra.destruction as pkg

    root = pathlib.Path(pkg.__file__).parent
    forbidden = (
        "time.time(",
        "datetime.now(",
        "utcnow(",
        "uuid",
        "random.Random(",
        "os.urandom",
        "secrets.",
    )
    offenders = []
    for f in sorted(root.glob("*.py")):
        src = f.read_text()
        for tok in forbidden:
            if tok in src:
                offenders.append(f"{f.name}:{tok}")
    assert offenders == []


def test_full_result_determinism_across_processes_style_runs():
    # Two independent system instances with no shared state must produce
    # byte-identical serialized results.
    ev = _make_event(impactor_mass_kg=1e22)
    r1 = _sys().execute_impact(ev, seed=4242)
    r2 = _sys().execute_impact(ev, seed=4242)
    assert json.dumps(result_to_dict(r1), sort_keys=True) == json.dumps(
        result_to_dict(r2), sort_keys=True
    )


def test_grazing_threshold_boundary():
    # cos(incidence) == 0.8 (> 0.15): must NOT be classified as grazing.
    s = _sys()
    ev = _make_event(impactor_velocity=Vec3(-1.6e4, 1.2e4, 0.0))  # slope 3-4-5
    r = s.execute_impact(ev, seed=34)
    assert not r.geometry.is_grazing
    assert math.isclose(
        math.cos(r.geometry.incidence_angle_rad), 0.8, rel_tol=0, abs_tol=1e-12
    )


def test_vector_and_scalar_edge_values():
    # -0.0 is accepted (finite), subnormals are accepted.
    ev = _make_event(impactor_velocity=Vec3(-2.0e4, -0.0, 5e-323))
    r = _sys().execute_impact(ev, seed=35)
    assert r.geometry.incoming_direction.is_finite()
    # sim_time of 0 is valid (first tick).
    ev0 = _make_event(impact_id="imp-t0", sim_time_s=0.0)
    r0 = _sys().execute_impact(ev0, seed=36)
    assert r0.event.sim_time_s == 0.0


# ------------------------------------------------ adversarial secondary impacts


def test_negative_recursion_depth_rejected():
    s = _sys()
    with pytest.raises(NumericalError):
        s.execute_impact(_make_event(), seed=1, recursion_depth=-1)


def test_secondary_wrong_parent_type_rejected():
    from astra.destruction import SecondaryTarget

    s = _sys()
    moon = SecondaryTarget(
        body_id="moon", mass_kg=7.3e22,
        position=Vec3(3.84e8, 0.0, 0.0), velocity=Vec3(0.0, 0.0, 0.0),
        radius_m=1.7e6,
    )
    with pytest.raises(ImpactValidationError):
        s.execute_secondary_impacts(
            _make_event(), targets=[moon], seed=1  # type: ignore[arg-type]
        )


def test_secondary_negative_cap_rejected():
    from astra.destruction import SecondaryTarget

    s = _sys()
    parent = s.execute_impact(_make_event(impactor_mass_kg=1e22), seed=1)
    moon = SecondaryTarget(
        body_id="moon", mass_kg=7.3e22,
        position=Vec3(3.84e8, 0.0, 0.0), velocity=Vec3(0.0, 0.0, 0.0),
        radius_m=1.7e6,
    )
    with pytest.raises(NumericalError):
        s.execute_secondary_impacts(parent, targets=[moon], seed=1, max_secondary=-1)


def test_secondary_recursion_depth_out_of_range():
    from astra.destruction import SecondaryTarget

    s = _sys()
    parent = s.execute_impact(_make_event(impactor_mass_kg=1e22), seed=1)
    moon = SecondaryTarget(
        body_id="moon", mass_kg=7.3e22,
        position=Vec3(3.84e8, 0.0, 0.0), velocity=Vec3(0.0, 0.0, 0.0),
        radius_m=1.7e6,
    )
    with pytest.raises(LimitExceededError):
        s.execute_secondary_impacts(
            parent, targets=[moon], seed=1, recursion_depth=99
        )
    with pytest.raises(LimitExceededError):
        s.execute_secondary_impacts(
            parent, targets=[moon], seed=1, recursion_depth=-1
        )
    with pytest.raises(NumericalError):
        s.execute_secondary_impacts(
            parent, targets=[moon], seed=1, recursion_depth=1.5  # type: ignore[arg-type]
        )


def test_secondary_target_validation():
    from astra.destruction import SecondaryTarget

    with pytest.raises(NumericalError):
        SecondaryTarget(
            body_id="x", mass_kg=0.0,
            position=Vec3(0.0, 0.0, 0.0), velocity=Vec3(0.0, 0.0, 0.0),
        )
    with pytest.raises(NumericalError):
        SecondaryTarget(
            body_id="x", mass_kg=1.0,
            position=Vec3(float("nan"), 0.0, 0.0), velocity=Vec3(0.0, 0.0, 0.0),
        )
    with pytest.raises(NumericalError):
        SecondaryTarget(
            body_id="x", mass_kg=1.0,
            position=Vec3(0.0, 0.0, 0.0), velocity=Vec3(0.0, 0.0, 0.0),
            radius_m=-5.0,
        )
    with pytest.raises(NumericalError):
        SecondaryTarget(
            body_id="", mass_kg=1.0,
            position=Vec3(0.0, 0.0, 0.0), velocity=Vec3(0.0, 0.0, 0.0),
        )


def test_secondary_authority_denied():
    from astra.destruction import SecondaryTarget

    parent = _sys().execute_impact(_make_event(impactor_mass_kg=1e22), seed=2)
    s = _sys(authority=_DenyAll())
    moon = SecondaryTarget(
        body_id="moon", mass_kg=7.3e22,
        position=Vec3(3.84e8, 0.0, 0.0), velocity=Vec3(0.0, 0.0, 0.0),
        radius_m=1.7e6,
    )
    with pytest.raises(AuthorityError):
        s.execute_secondary_impacts(parent, targets=[moon], seed=2)


def test_secondary_skips_comoving_pairs():
    from astra.destruction import SecondaryTarget
    import dataclasses

    r = _sys().execute_impact(_make_event(impactor_mass_kg=1e22), seed=3)
    f = r.fragments[0]
    # Target placed exactly on the fragment's future path but co-moving with
    # it: relative speed zero -> never an impact.
    comoving = SecondaryTarget(
        body_id="ghost", mass_kg=1.0e20,
        position=f.position + f.velocity * 100.0,
        velocity=f.velocity,
        radius_m=1.0e9,
    )
    parent = dataclasses.replace(r, fragments=r.fragments[:1])
    s = _sys()
    assert s.execute_secondary_impacts(parent, targets=[comoving], seed=4) == ()


def _engineered_parent_result_adv():
    """Local copy of the engineered parent (test files are not importable)."""
    import dataclasses

    from astra.destruction import FragmentState, SecondaryTarget

    ev = ImpactEvent(
        impact_id="imp-parent-adv",
        impactor_id="ast-1",
        target_id="earth",
        sim_time_s=1000.0,
        impactor_mass_kg=1.0e20,
        target_mass_kg=5.972e24,
        impactor_position=Vec3(6.471e6, 0.0, 0.0),
        target_position=Vec3(0.0, 0.0, 0.0),
        impactor_velocity=Vec3(-5e4, 0.0, 0.0),
        target_velocity=Vec3(0.0, 0.0, 0.0),
        target_radius_m=6.371e6,
    )
    r = _sys().execute_impact(ev, seed=500)
    moon = SecondaryTarget(
        body_id="moon",
        mass_kg=7.342e22,
        position=Vec3(3.84e8, 0.0, 0.0),
        velocity=Vec3(0.0, 0.0, 0.0),
        radius_m=1.737e6,
    )
    frags = (
        FragmentState(
            fragment_id="fa", parent_id="earth", impact_id=ev.impact_id,
            mass_kg=1.0e18, position=Vec3(1.0e7, 0.0, 0.0),
            velocity=Vec3(3.0e3, 0.0, 0.0), created_at_s=1000.0,
        ),
        FragmentState(
            fragment_id="fb", parent_id="earth", impact_id=ev.impact_id,
            mass_kg=2.0e18, position=Vec3(1.0e7, 1.0e6, 0.0),
            velocity=Vec3(3.0e3, 0.0, 0.0), created_at_s=1000.0,
        ),
        FragmentState(
            fragment_id="fc", parent_id="earth", impact_id=ev.impact_id,
            mass_kg=3.0e18, position=Vec3(-1.0e7, 0.0, 0.0),
            velocity=Vec3(-3.0e3, 0.0, 0.0), created_at_s=1000.0,
        ),
    )
    return dataclasses.replace(r, fragments=frags), moon


def test_secondary_targets_accepts_generator():
    parent, moon = _engineered_parent_result_adv()
    s = _sys()
    kids = s.execute_secondary_impacts(
        parent, targets=(t for t in [moon]), seed=900
    )
    assert len(kids) == 2


def test_secondary_cap_zero_returns_empty():
    parent, moon = _engineered_parent_result_adv()
    s = _sys()
    assert (
        s.execute_secondary_impacts(parent, targets=[moon], seed=900, max_secondary=0)
        == ()
    )
