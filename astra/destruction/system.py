"""DestructionSystem — orchestrates impact validation, energy/momentum
budgets, damage-state transitions, fragmentation, ejecta, and debris
registration.

Determinism contract
--------------------
- All randomness flows through a single ``RNGProvider`` per impact: either
  the caller-injected ``rng`` (e.g. an ``astra.core.rng.RNGStream`` owned by
  a long-lived core ``DeterministicRNG``, replayable via core snapshots) or
  a fresh core stream built from the ``seed`` argument
  (``fragmentation.make_impact_rng``). Same seed + same event + same config
  => identical ImpactResult.
- No global RNG. No wall-clock reads. No UUID-derived physics: all IDs are
  derived deterministically from caller-supplied impact/target IDs.

Authority contract
------------------
Every state-changing public method requires an AuthorityProvider. If none is
configured the call is REFUSED (fail-closed) — destruction never silently
mutates. Use ``adapters.CoreAuthorityProvider`` to gate through real
``astra.core.threading.AuthorityContext``.

Atomicity
---------
``execute_impact`` is atomic with respect to the damage ledger: if any
validation, limit, or entity/world registration fails, the target's damage
state is left untouched. (External side effects performed by caller-supplied
registrars before the failure — if any — are the registrars' own concern;
registration runs AFTER all physics and limits succeed.)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from astra.mathematics import Vector3

from .config import DestructionConfig
from .damage import DamageState, order, transition
from .ejecta import generate_ejecta
from .energy import compute_impact_energy
from .errors import (
    AuthorityError,
    ImpactValidationError,
    LimitExceededError,
    NumericalError,
)
from .fragmentation import (
    FragmentationInput,
    RNGProvider,
    fragment_target,
    make_impact_rng,
)
from .geometry import compute_impact_geometry
from .integration import (
    AuthorityProvider,
    CelestialResolver,
    EntityRegistrar,
    EventPublisher,
    PersistenceHook,
    PhysicsAdapter,
    WorldRegistrar,
)
from .momentum import compute_impact_momentum
from .persistence import damage_ledger_from_dict, damage_ledger_to_dict
from .provenance import DataProvenance
from .types import (
    DebrisState,
    FragmentState,
    ImpactEvent,
    ImpactResult,
)
from .validation import require_non_negative, require_positive

OP_SET_DAMAGE = "destruction.set_damage_state"
OP_EXECUTE = "destruction.execute_impact"
OP_SECONDARY = "destruction.execute_secondary_impacts"
OP_RESTORE = "destruction.restore_damage_ledger"

_MISSING = object()


@dataclass
class DestructionSystem:
    """Main entry point for destruction & impact simulation."""

    config: DestructionConfig = field(default_factory=DestructionConfig)

    # Injected dependencies (all optional; see integration.py protocols and
    # adapters.py for real implementations backed by astra.core et al.).
    authority: Optional[AuthorityProvider] = None
    rng: Optional[RNGProvider] = None
    entities: Optional[EntityRegistrar] = None
    events: Optional[EventPublisher] = None
    persistence: Optional[PersistenceHook] = None
    world: Optional[WorldRegistrar] = None
    celestial: Optional[CelestialResolver] = None
    physics: Optional[PhysicsAdapter] = None

    _damage_state: Dict[str, DamageState] = field(default_factory=dict, init=False)
    _impacts_executed: int = field(default=0, init=False)
    _entity_creation_count: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self.config.validate()

    # ------------------------------------------------------------------ API

    def get_damage_state(self, object_id: str) -> DamageState:
        return self._damage_state.get(object_id, DamageState.INTACT)

    def set_damage_state(self, object_id: str, state: DamageState) -> None:
        self._require_authority(OP_SET_DAMAGE)
        if not isinstance(state, DamageState):
            raise ImpactValidationError("state must be a DamageState member")
        self._damage_state[object_id] = state

    def validate_impact(self, event: ImpactEvent) -> None:
        """Raise if the impact event is not physically executable.

        Note: ImpactEvent construction already enforces finite vectors and
        non-negative radii; this layer enforces the *impact-level* contract.
        """
        if not event.impact_id:
            raise ImpactValidationError("impact_id must be non-empty")
        if not event.impactor_id or not event.target_id:
            raise ImpactValidationError("impactor_id and target_id required")
        if event.impactor_id == event.target_id:
            raise ImpactValidationError("impactor and target must differ")
        require_positive("impactor_mass_kg", event.impactor_mass_kg)
        require_positive("target_mass_kg", event.target_mass_kg)
        require_non_negative("sim_time_s", event.sim_time_s)
        if event.relative_speed() < self.config.limits.min_relative_speed_m_s:
            raise ImpactValidationError(
                f"relative speed {event.relative_speed()} below minimum "
                f"{self.config.limits.min_relative_speed_m_s}"
            )
        # Geometry sanity: raises on degenerate configurations.
        compute_impact_geometry(event, self.config)

    def execute_impact(
        self,
        event: ImpactEvent,
        *,
        seed: int,
        ejecta_mass_fraction: float = 0.05,
        characteristic_ejecta_speed_m_s: float = 100.0,
        recursion_depth: int = 0,
    ) -> ImpactResult:
        """Execute a single impact deterministically and atomically."""
        self._require_authority(OP_EXECUTE)
        self.validate_impact(event)

        if isinstance(recursion_depth, bool) or not isinstance(recursion_depth, int):
            raise NumericalError("recursion_depth must be an int")
        if recursion_depth > self.config.limits.max_recursion_depth:
            raise LimitExceededError(
                f"recursion depth {recursion_depth} exceeds "
                f"{self.config.limits.max_recursion_depth}"
            )

        energy = compute_impact_energy(event, self.config)
        if energy.kinetic_energy_j < self.config.limits.min_impact_energy_j:
            raise LimitExceededError(
                f"impact energy {energy.kinetic_energy_j} J below minimum "
                f"{self.config.limits.min_impact_energy_j} J"
            )

        # Optional cross-check against astra.physics: the CM reduced-mass KE
        # can never exceed the impactor's lab-frame body KE (m_red <= m1).
        # Violations indicate an integration bug; the adapter value itself is
        # NOT substituted (different physical quantity by definition).
        if self.physics is not None:
            ke_adapter = self.physics.kinetic_energy_j(
                event.impactor_mass_kg, event.relative_velocity()
            )
            if energy.kinetic_energy_j > ke_adapter + 1e-6 * max(ke_adapter, 1.0):
                raise NumericalError(
                    "reduced-mass kinetic energy exceeds physics-layer body "
                    "kinetic energy (invariant violation)"
                )
            if ke_adapter < self.config.limits.min_impact_energy_j:
                raise LimitExceededError("physics-derived energy below minimum")

        momentum = compute_impact_momentum(event, self.config)
        geometry = compute_impact_geometry(event, self.config)

        before = self.get_damage_state(event.target_id)
        after = self._decide_damage(before, energy, event)

        rng = self.rng if self.rng is not None else make_impact_rng(
            seed, self.config.rng_stream_name
        )

        fragments: Tuple[FragmentState, ...] = ()
        if after in (DamageState.FRACTURED, DamageState.FRAGMENTED, DamageState.DESTROYED):
            fragments = fragment_target(
                FragmentationInput(
                    event=event,
                    energy=energy,
                    target_state=after,
                    seed=seed,
                    target_radius_m=event.target_radius_m,
                ),
                self.config,
                rng,
            )
            if len(fragments) > self.config.limits.max_fragments_per_impact:
                raise LimitExceededError(
                    "fragment limit exceeded: "
                    f"{len(fragments)} > {self.config.limits.max_fragments_per_impact}"
                )

        ejecta = generate_ejecta(
            event,
            energy,
            rng,
            self.config,
            ejecta_mass_fraction=ejecta_mass_fraction,
            characteristic_speed_m_s=characteristic_ejecta_speed_m_s,
        )

        debris: List[DebrisState] = []
        for f in fragments:
            debris.append(
                DebrisState(
                    debris_id=f"{f.fragment_id}:debris",
                    origin_impact_id=event.impact_id,
                    mass_kg=f.mass_kg,
                    position=f.position,
                    velocity=f.velocity,
                    created_at_s=event.sim_time_s,
                    is_ejecta=False,
                )
            )
        for p in ejecta:
            debris.append(
                DebrisState(
                    debris_id=f"{p.ejecta_id}:debris",
                    origin_impact_id=event.impact_id,
                    mass_kg=p.mass_kg,
                    position=p.position,
                    velocity=p.velocity,
                    created_at_s=event.sim_time_s,
                    is_ejecta=True,
                )
            )
        if len(debris) > self.config.limits.max_debris_per_impact:
            raise LimitExceededError(
                f"debris count {len(debris)} exceeds limit "
                f"{self.config.limits.max_debris_per_impact}"
            )

        # ---- point of no return: all computation and limits succeeded ----
        previous = self._damage_state.get(event.target_id, _MISSING)
        try:
            self._damage_state[event.target_id] = after
            self._register_entities(event, fragments, ejecta, debris)
        except Exception:
            if previous is _MISSING:
                self._damage_state.pop(event.target_id, None)
            else:
                self._damage_state[event.target_id] = previous  # type: ignore[assignment]
            raise

        self._impacts_executed += 1

        result = ImpactResult(
            event=event,
            geometry=geometry,
            energy=energy,
            momentum=momentum,
            target_state_before=before,
            target_state_after=after,
            fragments=fragments,
            ejecta=ejecta,
            debris=tuple(debris),
            rng_seed_used=seed,
            model_version=self.config.model_version,
            provenance=DataProvenance.SIMULATED_DATA,
        )

        self._publish_event(
            "destruction.impact.executed",
            {
                "impact_id": event.impact_id,
                "target_id": event.target_id,
                "impactor_id": event.impactor_id,
                "state_before": before.value,
                "state_after": after.value,
                "fragment_count": len(fragments),
                "ejecta_count": len(ejecta),
            },
        )
        return result

    def execute_secondary_impacts(
        self,
        parent_event: ImpactEvent,
        *,
        seed: int,
        max_secondary: Optional[int] = None,
    ) -> Tuple[ImpactResult, ...]:
        """Bounded secondary-impact execution.

        Returns () in this revision: synthesising fragment/target collisions
        requires the collision-detection layer (a World/Physics concern, not
        a destruction concern). Callers that derive secondary ImpactEvents
        themselves (e.g. from world spatial queries) can pass them to
        execute_impact with an incremented ``recursion_depth``. This method
        exists to keep the authority/limits surface explicit.
        """
        self._require_authority(OP_SECONDARY)
        cap = (
            max_secondary
            if max_secondary is not None
            else self.config.limits.max_secondary_impacts
        )
        if cap < 0:
            raise NumericalError("max_secondary must be >= 0")
        return ()

    # ------------------------------------------------------- persistence

    def damage_ledger_snapshot(self) -> Dict[str, str]:
        """JSON-serialisable snapshot of the damage ledger (deterministic)."""
        return damage_ledger_to_dict(self._damage_state)

    def restore_damage_ledger(self, snapshot: Dict[str, str]) -> None:
        """Restore the damage ledger from a snapshot (authority-gated)."""
        self._require_authority(OP_RESTORE)
        self._damage_state = damage_ledger_from_dict(snapshot)

    def save_result(self, key: str, result: ImpactResult) -> None:
        """Persist an ImpactResult through the configured PersistenceHook."""
        self._require_authority(OP_EXECUTE)
        if self.persistence is None:
            raise ImpactValidationError("no PersistenceHook configured")
        from .persistence import result_to_dict

        self.persistence.save(key, result_to_dict(result))

    # ----------------------------------------------------------- internals

    def _require_authority(self, operation: str) -> None:
        if self.authority is None:
            raise AuthorityError(
                f"no AuthorityProvider configured; cannot perform {operation}",
                operation=operation,
            )
        self.authority.require(operation)

    def _decide_damage(self, before: DamageState, energy, event: ImpactEvent) -> DamageState:
        """Deterministic damage decision from specific deposited energy.

        Thresholds are MODEL PARAMETERS (J/kg of target mass, SIMULATED_DATA);
        they are orders-of-magnitude stand-ins for material-dependent
        disruption thresholds, which belong to a future material model.
        """
        if event.target_mass_kg <= 0.0:
            raise NumericalError("target mass must be positive")
        specific = energy.deposited_energy_j / event.target_mass_kg
        if specific < 1.0e3:
            wanted = DamageState.DAMAGED
        elif specific < 1.0e5:
            wanted = DamageState.FRACTURED
        elif specific < 1.0e7:
            wanted = DamageState.FRAGMENTED
        else:
            wanted = DamageState.DESTROYED
        if order(wanted) < order(before):
            return before  # never move backwards
        return transition(before, wanted)

    def _register_entities(self, event, fragments, ejecta, debris) -> None:
        if self.entities is not None:
            created = 0
            for f in fragments:
                self.entities.register(
                    f.fragment_id, "fragment", {"mass_kg": f.mass_kg}
                )
                created += 1
            for p in ejecta:
                self.entities.register(p.ejecta_id, "ejecta", {"mass_kg": p.mass_kg})
                created += 1
            for d in debris:
                self.entities.register(d.debris_id, "debris", {"mass_kg": d.mass_kg})
                created += 1
            self._entity_creation_count += created
        if self.world is not None:
            for d in debris:
                self.world.register_object(
                    d.debris_id,
                    d.position.to_tuple(),
                    {"origin_impact_id": d.origin_impact_id},
                )

    def _publish_event(self, topic: str, payload: dict) -> None:
        if self.events is not None:
            self.events.publish(topic, payload)

    # -------------------------------------------------------- diagnostics

    def diagnostics(self) -> Dict[str, object]:
        return {
            "impacts_executed": self._impacts_executed,
            "entities_created": self._entity_creation_count,
            "tracked_damage_states": len(self._damage_state),
            "model_version": self.config.model_version,
        }
