"""ASTRA Evolution — evolution state, events, histories, populations.

All objects are immutable value types.  History is preserved through
explicit event records that link source and resulting object identifiers;
no identity is silently destroyed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Tuple

from .errors import EvolutionNumericalError
from .provenance import Provenance, Quantity


def _finite_time(name: str, v) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise EvolutionNumericalError(f"{name} must be numeric, got {v!r}")
    fv = float(v)
    if math.isnan(fv) or math.isinf(fv):
        raise EvolutionNumericalError(f"{name} must be finite, got {fv!r}")
    return fv


# ---------------------------------------------------------------------------
# Stellar lifecycle
# ---------------------------------------------------------------------------

class StellarPhase(str, Enum):
    """Stellar evolutionary phase (kind, not hard-coded timescale)."""

    FORMATION = "FORMATION"
    MAIN_SEQUENCE = "MAIN_SEQUENCE"
    POST_MAIN_SEQUENCE = "POST_MAIN_SEQUENCE"
    REMNANT = "REMNANT"
    # Remnant sub-phases
    WHITE_DWARF = "WHITE_DWARF"
    NEUTRON_STAR = "NEUTRON_STAR"
    BLACK_HOLE = "BLACK_HOLE"
    UNKNOWN = "UNKNOWN"


class StellarTransitionTrigger(str, Enum):
    """Physical cause of a stellar phase transition."""

    NUCLEAR_BURNING = "NUCLEAR_BURNING"
    CORE_COLLAPSE = "CORE_COLLAPSE"
    MASS_LOSS = "MASS_LOSS"
    MERGER = "MERGER"
    ACCRETION = "ACCRETION"
    MODEL_STEP = "MODEL_STEP"
    CUSTOM = "CUSTOM"


@dataclass(frozen=True)
class StellarTransition:
    """Record of a lifecycle transition with full provenance."""

    before_phase: StellarPhase
    after_phase: StellarPhase
    trigger: StellarTransitionTrigger
    timescale_gyr: float
    model_id: str
    provenance: Provenance
    uncertainty: Optional[float] = None


# ---------------------------------------------------------------------------
# Galaxy morphology
# ---------------------------------------------------------------------------

class GalaxyMorphology(str, Enum):
    """Morphological class; evolution carries a probability distribution where
    the model supports it (see ``GalaxyState.morphology_probs``).
    """

    SPIRAL = "SPIRAL"
    LENTICULAR = "LENTICULAR"
    ELLIPTICAL = "ELLIPTICAL"
    IRREGULAR = "IRREGULAR"
    INTERACTING = "INTERACTING"
    UNKNOWN = "UNKNOWN"


class StructureRegime(str, Enum):
    """Binding regime for large-scale structures (§2.17)."""

    GRAVITATIONALLY_BOUND = "GRAVITATIONALLY_BOUND"
    EXPANDING_ASSOCIATION = "EXPANDING_ASSOCIATION"
    DISSOLVING = "DISSOLVING"
    UNKNOWN = "UNKNOWN"


class AGNActivity(str, Enum):
    """Long-term AGN activity state (§2.14)."""

    INACTIVE = "INACTIVE"
    LOW_ACTIVITY = "LOW_ACTIVITY"
    ACTIVE = "ACTIVE"
    HIGH_ACTIVITY = "HIGH_ACTIVITY"


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

class EvolutionEventKind(str, Enum):
    """Kind of evolutionary event (§2.27)."""

    STELLAR_TRANSITION = "STELLAR_TRANSITION"
    STELLAR_DEATH = "STELLAR_DEATH"
    GALAXY_MERGER = "GALAXY_MERGER"
    CLUSTER_MERGER = "CLUSTER_MERGER"
    BLACK_HOLE_MERGER = "BLACK_HOLE_MERGER"
    STAR_FORMATION_TRANSITION = "STAR_FORMATION_TRANSITION"
    POPULATION_TRANSITION = "POPULATION_TRANSITION"
    COSMIC_STRUCTURE_TRANSITION = "COSMIC_STRUCTURE_TRANSITION"
    CHEMICAL_ENRICHMENT = "CHEMICAL_ENRICHMENT"
    MORPHOLOGY_TRANSITION = "MORPHOLOGY_TRANSITION"
    AGN_TRANSITION = "AGN_TRANSITION"
    VOID_EVOLUTION = "VOID_EVOLUTION"
    CUSTOM = "CUSTOM"


@dataclass(frozen=True)
class EvolutionEvent:
    """Immutable record of a single evolutionary event.

    Preserves: timestamp, source/resulting objects, physical cause,
    provenance, causal parent linkage.
    """

    event_id: str
    kind: EvolutionEventKind
    cosmic_time_gyr: float  # cosmic time of the event
    source_object_ids: Tuple[str, ...]
    resulting_object_ids: Tuple[str, ...]
    physical_cause: str
    model_id: str
    provenance: Provenance
    causal_parent_event_id: Optional[str] = None
    metadata: Dict[str, object] = field(default_factory=dict)

    def __post_init__(self):
        if not self.event_id or not isinstance(self.event_id, str):
            raise ValueError("event_id must be a non-empty string")
        if not isinstance(self.kind, EvolutionEventKind):
            raise TypeError("kind must be an EvolutionEventKind")
        object.__setattr__(self, "cosmic_time_gyr",
                           _finite_time("cosmic_time_gyr", self.cosmic_time_gyr))
        if not isinstance(self.physical_cause, str) or not self.physical_cause:
            raise ValueError("physical_cause must be a non-empty string")
        if not isinstance(self.model_id, str) or not self.model_id:
            raise ValueError("model_id must be a non-empty string")
        if not isinstance(self.provenance, Provenance):
            raise TypeError("provenance must be a Provenance")
        object.__setattr__(self, "source_object_ids", tuple(self.source_object_ids))
        object.__setattr__(self, "resulting_object_ids", tuple(self.resulting_object_ids))


# ---------------------------------------------------------------------------
# Evolution states
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EvolutionState:
    """Full state of an evolving object at a point in cosmic time.

    Attributes:
        object_id: stable identifier preserved across transitions.
        cosmic_time_gyr: cosmic time (Gyr) of this snapshot.
        phase: phase label (e.g. ``"MAIN_SEQUENCE"`` or ``"SPIRAL"``).
        quantities: physical quantities each carrying provenance.
        model_id: model that produced this state.
        provenance: overall provenance of this snapshot.
        metadata: free-form additional data (morphology probs, regime, etc.).
    """

    object_id: str
    cosmic_time_gyr: float
    phase: str
    quantities: Dict[str, Quantity]
    model_id: str
    provenance: Provenance
    metadata: Dict[str, object] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.object_id, str) or not self.object_id:
            raise ValueError("object_id must be a non-empty string")
        object.__setattr__(self, "cosmic_time_gyr",
                           _finite_time("cosmic_time_gyr", self.cosmic_time_gyr))
        if not isinstance(self.phase, str) or not self.phase:
            raise ValueError("phase must be a non-empty string")
        if not isinstance(self.model_id, str) or not self.model_id:
            raise ValueError("model_id must be a non-empty string")
        if not isinstance(self.provenance, Provenance):
            raise TypeError("provenance must be a Provenance")
        if not isinstance(self.quantities, dict):
            raise TypeError("quantities must be a dict")
        for k, v in self.quantities.items():
            if not isinstance(k, str):
                raise TypeError("quantity keys must be strings")
            if not isinstance(v, Quantity):
                raise TypeError(f"quantity {k!r} must be a Quantity")
        object.__setattr__(self, "quantities", dict(self.quantities))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True)
class StarFormationHistory:
    """SFH over cosmic time; list of (cosmic_time_gyr, sfr_msun_per_yr)."""

    object_id: str
    samples: Tuple[Tuple[float, float], ...]
    model_id: str
    provenance: Provenance

    def __post_init__(self):
        if not isinstance(self.object_id, str) or not self.object_id:
            raise ValueError("object_id required")
        for t, sfr in self.samples:
            _finite_time("sfh.time", t)
            _finite_time("sfh.sfr", sfr)
            if sfr < 0.0:
                raise EvolutionNumericalError("SFR must be >= 0")
        object.__setattr__(self, "samples", tuple(tuple(s) for s in self.samples))


@dataclass(frozen=True)
class MetallicityHistory:
    """Metallicity over cosmic time; list of (cosmic_time_gyr, Z)."""

    object_id: str
    samples: Tuple[Tuple[float, float], ...]
    model_id: str
    provenance: Provenance

    def __post_init__(self):
        if not isinstance(self.object_id, str) or not self.object_id:
            raise ValueError("object_id required")
        for t, z in self.samples:
            _finite_time("metallicity.time", t)
            _finite_time("metallicity.Z", z)
            if z < 0.0:
                raise EvolutionNumericalError("metallicity Z must be >= 0")


@dataclass(frozen=True)
class PopulationState:
    """Reduced-order representation of a stellar population (§2.7)."""

    population_id: str
    cosmic_time_gyr: float
    parent_object_id: str
    mass_function: Tuple[Tuple[float, float], ...]     # (mass_msun, weight)
    age_distribution: Tuple[Tuple[float, float], ...]  # (age_gyr, weight)
    remnant_fraction: float
    metallicity: float
    model_id: str
    provenance: Provenance

    def __post_init__(self):
        if not isinstance(self.population_id, str) or not self.population_id:
            raise ValueError("population_id required")
        _finite_time("cosmic_time_gyr", self.cosmic_time_gyr)
        object.__setattr__(self, "mass_function",
                           tuple(tuple(p) for p in self.mass_function))
        object.__setattr__(self, "age_distribution",
                           tuple(tuple(p) for p in self.age_distribution))
        rf = _finite_time("remnant_fraction", self.remnant_fraction)
        if not 0.0 <= rf <= 1.0:
            raise EvolutionNumericalError("remnant_fraction must be in [0,1]")
        _finite_time("metallicity", self.metallicity)
        if self.metallicity < 0.0:
            raise EvolutionNumericalError("metallicity must be >= 0")


# ---------------------------------------------------------------------------
# Galaxy / structure states (lightweight wrappers around EvolutionState)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GalaxyState:
    """Evolving galaxy state (§2.10–2.12).  Wraps common quantities with
    morphology probability distribution and AGN state.
    """

    galaxy_id: str
    cosmic_time_gyr: float
    stellar_mass: Quantity
    gas_mass: Quantity
    sfr: Quantity
    metallicity: Quantity
    morphology_probs: Dict[GalaxyMorphology, float]  # normalized
    agn_activity: AGNActivity
    central_bh_mass: Optional[Quantity] = None
    model_id: str = "unknown"
    provenance: Provenance = Provenance.SIMULATED_DATA
    regime: StructureRegime = StructureRegime.UNKNOWN

    def __post_init__(self):
        if not isinstance(self.galaxy_id, str) or not self.galaxy_id:
            raise ValueError("galaxy_id required")
        _finite_time("cosmic_time_gyr", self.cosmic_time_gyr)
        if not isinstance(self.morphology_probs, dict) or not self.morphology_probs:
            raise ValueError("morphology_probs must be a non-empty dict")
        total = sum(self.morphology_probs.values())
        if abs(total - 1.0) > 1e-6 and total != 0.0:
            raise EvolutionNumericalError(
                f"morphology_probs must sum to 1.0, got {total}"
            )
        for k, v in self.morphology_probs.items():
            if not isinstance(k, GalaxyMorphology):
                raise TypeError("morphology_probs keys must be GalaxyMorphology")
            _finite_time("morphology_prob", v)
            if not 0.0 <= v <= 1.0:
                raise EvolutionNumericalError("morphology prob must be in [0,1]")


@dataclass(frozen=True)
class ClusterState:
    """Galaxy cluster state (§2.16)."""

    cluster_id: str
    cosmic_time_gyr: float
    total_mass: Quantity
    member_ids: Tuple[str, ...]
    regime: StructureRegime
    model_id: str
    provenance: Provenance

    def __post_init__(self):
        if not isinstance(self.cluster_id, str) or not self.cluster_id:
            raise ValueError("cluster_id required")
        _finite_time("cosmic_time_gyr", self.cosmic_time_gyr)
        object.__setattr__(self, "member_ids", tuple(self.member_ids))


@dataclass(frozen=True)
class CosmicWebState:
    """Cosmic-web state (§2.19): connectivity and component regimes."""

    web_id: str
    cosmic_time_gyr: float
    filament_count: int
    node_count: int
    void_count: int
    regime: StructureRegime
    model_id: str
    provenance: Provenance

    def __post_init__(self):
        if not isinstance(self.web_id, str) or not self.web_id:
            raise ValueError("web_id required")
        _finite_time("cosmic_time_gyr", self.cosmic_time_gyr)
        for name in ("filament_count", "node_count", "void_count"):
            v = getattr(self, name)
            if not isinstance(v, int) or v < 0:
                raise EvolutionNumericalError(f"{name} must be int >= 0")


@dataclass(frozen=True)
class VoidState:
    """Void state (§2.18): size, density contrast, expansion."""

    void_id: str
    cosmic_time_gyr: float
    radius_mpc: Quantity
    density_contrast: Quantity  # delta = (rho - rho_mean)/rho_mean
    regime: StructureRegime
    model_id: str
    provenance: Provenance

    def __post_init__(self):
        if not isinstance(self.void_id, str) or not self.void_id:
            raise ValueError("void_id required")
        _finite_time("cosmic_time_gyr", self.cosmic_time_gyr)
