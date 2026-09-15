"""ASTRA COSMOS — Phase 21: evolution state containers.

This module defines the STATE vocabulary of the Long-Term Cosmic Evolution
Engine:

- ``EvolutionState``: the full evolving state of ONE object (a star, a
  stellar population, a galaxy, a cluster, a cosmic-web region) at one
  cosmic time. Frozen value object; the engine advances it by producing a
  new instance (copy-on-write), never by mutating.
- ``PopulationState``: reduced-order stellar-population summary (mass
  function, age distribution, remnant fraction, metallicity).
- ``StarFormationHistory`` / ``MetallicityHistory``: immutable sampled
  histories over cosmic time.
- Lifecycle / activity / regime enums used as state ``phase`` labels.

Identity, provenance and history policy (spec 2.28): an EvolutionState
carries its object_id, its PROGENITOR references (parent_object_ids) and
its provenance. Changing state never destroys identity — the engine records
transitions as EvolutionEvents linking source and resulting ids.

Standard quantity keys (documented contract; models may add more):
    initial_mass_msun      star: zero-age main-sequence mass
    mass_msun              star: current (or remnant) mass
    age_gyr                time since formation of the object
    live_stellar_mass_msun population: mass still in living stars
    stellar_mass_msun      galaxy/cluster: living stellar mass
    gas_mass_msun          cold/available gas mass
    sfr_msun_yr            star-formation rate
    birth_rate_msun_yr     population: mass of stars born per year
    death_rate_msun_yr     population: stellar mass dying per year
    sn_mass_rate_msun_yr   core-collapse dying mass per year
    sn_number_proxy_per_gyr  ORDER-OF-MAGNITUDE core-collapse count proxy
    remnant_wd_msun / remnant_ns_msun / remnant_bh_msun
    remnant_mass_msun      aggregate remnant mass (any kind)
    metal_mass_msun        mass of metals in the gas reservoir
    metallicity_z          dimensionless gas metallicity (mass fraction)
    luminosity_lsun        bolometric luminosity proxy
    bh_mass_msun           central / total black-hole mass
    total_mass_msun        cluster total gravitating mass
    member_count           cluster member galaxy count
    void_volume_fraction, node_mass_fraction, filament_mass_fraction,
    sheet_mass_fraction, density_contrast_sigma, void_size_comoving_mpc,
    connectivity_index     cosmic-web summary quantities

Times: cosmic time is expressed in GIGAYEARS (Gyr) in this layer — the one
place ASTRA needs timescales far beyond floating-point comfort in seconds.
Conversion helpers to the SI-second world of astra.temporal live in
``astra.evolution.timebase``. No new clock type is introduced.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Dict, Mapping, Optional, Tuple

from astra.celestial.provenance import DataProvenance

from .errors import EvolutionValidationError
from .provenance import ProjectionClass
from .quantity import Quantity, require_finite_number


class StellarLifecyclePhase(str, Enum):
    """Stellar lifecycle phases (spec 2.6). Labels align with
    astra.celestial taxonomy; the DYNAMICS live here, the taxonomy there."""

    FORMATION = "FORMATION"
    MAIN_SEQUENCE = "MAIN_SEQUENCE"
    POST_MAIN_SEQUENCE = "POST_MAIN_SEQUENCE"
    REMNANT = "REMNANT"


class RemnantKind(str, Enum):
    """Remnant outcomes (spec 2.6); names align with ObjectCategory."""

    WHITE_DWARF = "WHITE_DWARF"
    NEUTRON_STAR = "NEUTRON_STAR"
    STELLAR_MASS_BLACK_HOLE = "STELLAR_MASS_BLACK_HOLE"


class AGNActivityState(str, Enum):
    """Long-term AGN activity states (spec 2.14). Model-driven transitions;
    no observational certainty is implied for speculative future activity."""

    INACTIVE = "INACTIVE"
    LOW_ACTIVITY = "LOW_ACTIVITY"
    ACTIVE = "ACTIVE"
    HIGH_ACTIVITY = "HIGH_ACTIVITY"


class StructureRegime(str, Enum):
    """Large-scale-structure expansion regime (spec 2.17). Decided per
    structure from supplied binding/expansion information — never assumed
    to be permanently bound."""

    GRAVITATIONALLY_BOUND = "GRAVITATIONALLY_BOUND"
    EXPANDING_ASSOCIATION = "EXPANDING_ASSOCIATION"
    DISSOLVING = "DISSOLVING"
    UNKNOWN = "UNKNOWN"


class MorphologyClass(str, Enum):
    """Galaxy morphology classes (spec 2.12). Carried as a probability
    DISTRIBUTION over these classes, never a hard assertion."""

    SPIRAL = "SPIRAL"
    LENTICULAR = "LENTICULAR"
    ELLIPTICAL = "ELLIPTICAL"
    IRREGULAR = "IRREGULAR"
    INTERACTING = "INTERACTING"


# Object kinds understood by the engine (resolution ladder, spec 2.30).
KIND_STAR = "STAR"
KIND_POPULATION = "POPULATION"
KIND_GALAXY = "GALAXY"
KIND_CLUSTER = "CLUSTER"
KIND_COSMIC_WEB = "COSMIC_WEB"
KIND_STRUCTURE = "STRUCTURE"  # generic named large-scale structure

_KIND_RANK = {
    KIND_STAR: 0,
    KIND_POPULATION: 1,
    KIND_GALAXY: 2,
    KIND_CLUSTER: 3,
    KIND_COSMIC_WEB: 4,
    KIND_STRUCTURE: 4,
}

_RESOLUTION_RANK = {
    "individual": 0,
    "population": 1,
    "galaxy": 2,
    "cluster": 3,
    "web": 4,
}

# Quantity keys recognized as baryonic constituency for epoch inputs.
_MASS_KEYS_LIVE = ("live_stellar_mass_msun", "stellar_mass_msun")
_REMNANT_KEYS = ("remnant_wd_msun", "remnant_ns_msun", "remnant_bh_msun", "remnant_mass_msun")


def resolution_rank(resolution: str) -> int:
    if resolution not in _RESOLUTION_RANK:
        raise EvolutionValidationError(f"unknown resolution {resolution!r}")
    return _RESOLUTION_RANK[resolution]


def kind_rank(kind: str) -> int:
    if kind not in _KIND_RANK:
        raise EvolutionValidationError(f"unknown object kind {kind!r}")
    return _KIND_RANK[kind]


@dataclass(frozen=True)
class EvolutionState:
    """Full evolving state of one object at one cosmic time.

    quantities: mapping of documented keys to Quantity. Treated as
    immutable by convention; engine code always copies before modifying.
    """

    object_id: str
    object_kind: str
    cosmic_time_gyr: float
    phase: str
    quantities: Dict[str, Quantity]
    model_id: str
    provenance: DataProvenance = DataProvenance.SIMULATED_DATA
    projection_class: ProjectionClass = ProjectionClass.NONE
    parent_object_ids: Tuple[str, ...] = ()
    metadata: Dict[str, object] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.object_id, str) or not self.object_id:
            raise EvolutionValidationError("object_id must be a non-empty string")
        if not isinstance(self.object_kind, str) or not self.object_kind:
            raise EvolutionValidationError("object_kind must be a non-empty string")
        object.__setattr__(
            self, "cosmic_time_gyr", require_finite_number(self.cosmic_time_gyr, "cosmic_time_gyr")
        )
        if self.cosmic_time_gyr < 0.0:
            raise EvolutionValidationError("cosmic_time_gyr must be >= 0")
        if not isinstance(self.phase, str) or not self.phase:
            raise EvolutionValidationError("phase must be a non-empty string label")
        if not isinstance(self.model_id, str) or not self.model_id:
            raise EvolutionValidationError("model_id must be a non-empty string")
        if not isinstance(self.provenance, DataProvenance):
            raise EvolutionValidationError("provenance must be a DataProvenance member")
        if not isinstance(self.projection_class, ProjectionClass):
            raise EvolutionValidationError("projection_class must be a ProjectionClass member")
        for key, q in self.quantities.items():
            if not isinstance(key, str) or not key:
                raise EvolutionValidationError("quantity keys must be non-empty strings")
            if not isinstance(q, Quantity):
                raise EvolutionValidationError(f"quantity {key!r} must be a Quantity")
        object.__setattr__(self, "parent_object_ids", tuple(self.parent_object_ids))

    def with_quantities(self, updates: Mapping[str, Quantity]) -> "EvolutionState":
        """Copy-on-write quantity update (identity and history preserved)."""
        merged = dict(self.quantities)
        for k, v in updates.items():
            merged[k] = v if isinstance(v, Quantity) else Quantity(value=v, unit="dimensionless")
        return replace(self, quantities=merged)

    def with_phase(self, phase: str) -> "EvolutionState":
        return replace(self, phase=phase)

    def quantity_value(self, key: str, default: Optional[float] = None) -> Optional[float]:
        q = self.quantities.get(key)
        return default if q is None else q.value

    def to_dict(self) -> Dict[str, object]:
        from .persistence import state_to_dict  # local import avoids a cycle

        return state_to_dict(self)

    @classmethod
    def from_dict(cls, d) -> "EvolutionState":
        from .persistence import state_from_dict

        return state_from_dict(d)


@dataclass(frozen=True)
class PopulationState:
    """Reduced-order stellar-population summary (spec 2.7).

    mass_function:     (mass_msun, weight) samples of the living-star mass
                       function (weights need not sum to 1; they are masses).
    age_distribution:  (age_gyr, weight_msun) living mass per age bracket.
    """

    population_id: str
    cosmic_time_gyr: float
    parent_object_id: str
    mass_function: Tuple[Tuple[float, float], ...]
    age_distribution: Tuple[Tuple[float, float], ...]
    remnant_fraction: float
    metallicity: float
    model_id: str
    provenance: DataProvenance = DataProvenance.SIMULATED_DATA

    def __post_init__(self):
        if not isinstance(self.population_id, str) or not self.population_id:
            raise EvolutionValidationError("population_id must be a non-empty string")
        require_finite_number(self.cosmic_time_gyr, "PopulationState.cosmic_time_gyr")
        if not isinstance(self.parent_object_id, str):
            raise EvolutionValidationError("parent_object_id must be a string")
        for label, samples in (
            ("mass_function", self.mass_function),
            ("age_distribution", self.age_distribution),
        ):
            for mass, weight in samples:
                require_finite_number(mass, f"PopulationState.{label} mass")
                require_finite_number(weight, f"PopulationState.{label} weight")
        require_finite_number(self.remnant_fraction, "PopulationState.remnant_fraction")
        require_finite_number(self.metallicity, "PopulationState.metallicity")

    @classmethod
    def from_evolution_state(cls, state: EvolutionState) -> "PopulationState":
        """Build the summary from a POPULATION-kind EvolutionState."""
        if state.object_kind != KIND_POPULATION:
            raise EvolutionValidationError(
                f"from_evolution_state requires a POPULATION state, got {state.object_kind}"
            )

        def _pairs(key: str) -> Tuple[Tuple[float, float], ...]:
            raw = state.metadata.get(key, ())
            return tuple((float(m), float(w)) for m, w in raw)

        live = sum(state.quantity_value(k, 0.0) for k in _MASS_KEYS_LIVE)
        remnants = sum(state.quantity_value(k, 0.0) for k in _REMNANT_KEYS)
        total = live + remnants
        return cls(
            population_id=state.object_id,
            cosmic_time_gyr=state.cosmic_time_gyr,
            parent_object_id=str(state.metadata.get("parent_object_id", "")),
            mass_function=_pairs("mass_function"),
            age_distribution=_pairs("age_distribution"),
            remnant_fraction=(remnants / total) if total > 0.0 else 0.0,
            metallicity=state.quantity_value("metallicity_z", 0.0),
            model_id=state.model_id,
            provenance=state.provenance,
        )


@dataclass(frozen=True)
class StarFormationHistory:
    """SFR over cosmic time; samples of (cosmic_time_gyr, sfr_msun_yr)."""

    object_id: str
    samples: Tuple[Tuple[float, float], ...]
    model_id: str
    provenance: DataProvenance = DataProvenance.SIMULATED_DATA

    def __post_init__(self):
        if not isinstance(self.object_id, str) or not self.object_id:
            raise EvolutionValidationError("object_id must be a non-empty string")
        for t, s in self.samples:
            require_finite_number(t, "StarFormationHistory time")
            require_finite_number(s, "StarFormationHistory sfr")

    @classmethod
    def from_history(cls, state: EvolutionState, key: str = "sfr_msun_yr") -> "StarFormationHistory":
        raw = state.metadata.get("history_" + key, ())
        return cls(
            object_id=state.object_id,
            samples=tuple((float(t), float(s)) for t, s in raw),
            model_id=state.model_id,
            provenance=state.provenance,
        )


@dataclass(frozen=True)
class MetallicityHistory:
    """Metallicity over cosmic time; samples of (cosmic_time_gyr, Z)."""

    object_id: str
    samples: Tuple[Tuple[float, float], ...]
    model_id: str
    provenance: DataProvenance = DataProvenance.SIMULATED_DATA

    def __post_init__(self):
        if not isinstance(self.object_id, str) or not self.object_id:
            raise EvolutionValidationError("object_id must be a non-empty string")
        for t, z in self.samples:
            require_finite_number(t, "MetallicityHistory time")
            require_finite_number(z, "MetallicityHistory metallicity")

    @classmethod
    def from_history(cls, state: EvolutionState, key: str = "metallicity_z") -> "MetallicityHistory":
        raw = state.metadata.get("history_" + key, ())
        return cls(
            object_id=state.object_id,
            samples=tuple((float(t), float(z)) for t, z in raw),
            model_id=state.model_id,
            provenance=state.provenance,
        )


__all__ = [
    "EvolutionState",
    "PopulationState",
    "StarFormationHistory",
    "MetallicityHistory",
    "StellarLifecyclePhase",
    "RemnantKind",
    "AGNActivityState",
    "StructureRegime",
    "MorphologyClass",
    "KIND_STAR",
    "KIND_POPULATION",
    "KIND_GALAXY",
    "KIND_CLUSTER",
    "KIND_COSMIC_WEB",
    "KIND_STRUCTURE",
    "resolution_rank",
    "kind_rank",
]
