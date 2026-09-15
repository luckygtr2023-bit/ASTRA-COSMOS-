"""ASTRA COSMOS — Phase 21: built-in reduced-order evolution models.

This module registers the engine's built-in models. EVERY numeric default
below is an explicit, configurable model parameter with a stated
assumption — none is asserted as exact reality (spec 2.8/2.10/2.37):
outputs are SIMULATED_DATA projections with declared uncertainties, and
each model's registry entry lists its assumptions, limitations, and
validity horizon. Where in-repo physics is missing (no Universe Evolution,
no Phase 20, no stellar-astrophysics engine) the model is honest about it
and the engine refuses rather than extrapolates silently.

Models
------
stellar.single_star_lifecycle.v1   STAR lifecycle FORMATION -> MAIN_SEQUENCE
                                   -> POST_MAIN_SEQUENCE -> REMNANT, with
                                   remnant kind/mass/luminosity assignment.
population.conveyor.v1             Population-level "conveyor-belt" model:
                                   cohort table per IMF mass bin, delayed
                                   deaths, remnant production, closed-box
                                   metal enrichment, luminosity evolution.
galaxy.one_zone.v1                 One-zone galaxy: gas-supply SFR, delayed
                                   recycling, closed-box enrichment, SMBH
                                   growth with an AGN activity-state machine
                                   and morphology distribution drift.
cluster.member_aggregate.v1        Cluster-level aggregation: member totals,
                                   accretion-driven mass growth, regime tag.
web.regime_evolution.v1            Cosmic-web regime evolution. REQUIRES a
                                   per-step expansion input (scale-factor
                                   ratio) from the injected
                                   UniverseEvolutionProvider or a caller-
                                   supplied function — it never computes
                                   expansion itself.

Determinism: no model uses randomness; identical inputs give bit-identical
outputs. The RNGProvider protocol exists for FUTURE stochastic models; the
built-ins are deliberately closed-form.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Dict, List, Optional, Tuple

from astra.celestial.provenance import DataProvenance

from .errors import (
    EvolutionDependencyError,
    EvolutionLimitationError,
    EvolutionValidationError,
)
from .limitations import LimitationState
from .models import (
    EvolutionModel,
    ModelAssumption,
    ModelClassification,
    ModelRegistry,
)
from .provenance import ProjectionClass
from .quantity import Quantity, require_finite_number
from .state import (
    AGNActivityState,
    EvolutionState,
    MorphologyClass,
    RemnantKind,
    StructureRegime,
    KIND_CLUSTER,
    KIND_COSMIC_WEB,
    KIND_GALAXY,
    KIND_POPULATION,
    KIND_STAR,
    KIND_STRUCTURE,
)

_MSUN_PER_GYR_TO_MSUN_YR = 1.0e-9  # Msun/Gyr -> Msun/yr

_NUMERICAL_MASS_FLOOR_MSUN = 1.0e-12


def _q(value: float, unit: str, note: str = "", uncertainty: Optional[float] = None) -> Quantity:
    return Quantity(
        value=value,
        unit=unit,
        provenance=DataProvenance.SIMULATED_DATA,
        uncertainty=uncertainty,
        note=note or None,
    )


# ==========================================================================
# Shared parameter block — every number is configuration with a stated role
# ==========================================================================
@dataclass(frozen=True)
class BuiltinModelParams:
    """Parameters of the built-in reduced-order models.

    Stellar group: order-of-magnitude power-law approximations; the
    exponents are fitted forms valid roughly for 0.5-50 Msun and are
    applied outside that range only as order-of-magnitude estimates
    (stated in the models' assumptions).
    """

    # --- stellar lifecycle -------------------------------------------------
    t_ms_sun_gyr: float = 10.0                  # main-sequence lifetime at 1 Msun
    ml_alpha: float = 2.5                       # t_MS ~ M^-alpha exponent
    ml_beta: float = 3.5                        # L ~ M^beta exponent
    post_ms_fraction: float = 0.1               # t_post = fraction of t_MS
    post_ms_luminosity_boost: float = 100.0     # crude post-MS luminosity factor
    m_ns_threshold_msun: float = 8.0            # >= this -> core collapse
    m_bh_threshold_msun: float = 20.0           # >= this -> stellar BH remnant
    remnant_wd_mass_msun: float = 0.6           # fixed-mass WD approximation
    remnant_ns_mass_msun: float = 1.4           # canonical NS mass
    remnant_bh_mass_fraction: float = 0.3       # BH mass as fraction of progenitor
    wd_luminosity_lsun: float = 1.0e-4          # order-of-magnitude early WD light
    ns_luminosity_lsun: float = 1.0e-6
    bh_luminosity_lsun: float = 0.0

    # --- initial mass function (Kroupa-2001-style two-slope defaults) ------
    imf_alpha_low: float = 1.3                  # dN/dm ~ m^-alpha below break
    imf_alpha_high: float = 2.3                 # above break
    imf_break_msun: float = 0.5
    imf_min_mass_msun: float = 0.08
    imf_max_mass_msun: float = 100.0
    population_bins: int = 24                   # log-spaced conveyor mass bins
    cohort_death_window_gyr: float = 0.1        # smooth turnoff width per bin
    max_cohorts_per_bin: int = 512              # coarsening budget per bin

    # --- population yields / recycling (closed-box approximations) ---------
    cc_yield: float = 0.02                      # fresh metals per CC dying mass
    sn_number_proxy_progenitor_msun: float = 10.0  # CC count proxy divisor

    # --- galaxy one-zone ----------------------------------------------------
    gas_depletion_time_gyr: float = 2.0         # SFR = gas / t_dep (linear law)
    stellar_return_time_gyr: float = 10.0       # delayed recycling timescale
    stellar_return_fraction: float = 0.3        # dying mass returned to gas
    galaxy_inflow_msun_yr: float = 0.0          # optional gas accretion
    mass_to_light_ratio: float = 1.0            # crude luminosity proxy
    bh_salpeter_time_gyr: float = 0.045         # e-folding at Eddington (eps=0.1)
    bh_eddington_ratio_high: float = 1.0
    bh_eddington_ratio_active: float = 0.3
    bh_eddington_ratio_low: float = 0.01
    bh_fuel_gas_fraction_per_gyr: float = 1.0e-3  # max gas fraction consumed /Gyr
    agn_fuel_active_threshold: float = 0.10     # gas fraction to be/remain active
    agn_fuel_inactive_threshold: float = 0.02   # gas fraction below -> inactive
    agn_hysteresis_margin: float = 0.02         # extra fuel needed to ignite
    morphology_relaxation_gyr: float = 5.0      # distribution drift timescale

    # --- cluster / cosmic web ------------------------------------------------
    cluster_accretion_msun_yr: float = 0.0      # optional accretion onto cluster
    web_growth_rate_per_gyr: float = 0.01       # bound-regime sigma growth
    web_decay_rate_per_gyr: float = 0.005       # dissolving-regime sigma decay
    web_transfer_rate_per_gyr: float = 0.005    # sheet->filament->node inflow
    void_volume_growth_per_gyr: float = 0.002   # void volume-fraction drift
    void_volume_fraction_max: float = 0.9
    connectivity_decay_per_gyr: float = 0.002   # expanding-regime connectivity
    connectivity_growth_per_gyr: float = 0.001  # bound-regime connectivity

    def validate(self) -> None:
        positive = [
            "t_ms_sun_gyr", "ml_alpha", "ml_beta", "post_ms_fraction",
            "post_ms_luminosity_boost", "m_ns_threshold_msun", "m_bh_threshold_msun",
            "imf_alpha_low", "imf_alpha_high", "imf_break_msun",
            "imf_min_mass_msun", "imf_max_mass_msun", "population_bins",
            "cohort_death_window_gyr", "sn_number_proxy_progenitor_msun",
            "gas_depletion_time_gyr", "stellar_return_time_gyr",
            "bh_salpeter_time_gyr", "morphology_relaxation_gyr",
            "web_growth_rate_per_gyr", "web_decay_rate_per_gyr",
            "web_transfer_rate_per_gyr", "void_volume_growth_per_gyr",
            "connectivity_decay_per_gyr", "connectivity_growth_per_gyr",
        ]
        for name in positive:
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0:
                raise EvolutionValidationError(f"BuiltinModelParams.{name} must be > 0")
        if self.m_bh_threshold_msun <= self.m_ns_threshold_msun:
            raise EvolutionValidationError(
                "BuiltinModelParams.m_bh_threshold_msun must exceed m_ns_threshold_msun"
            )
        for name in (
            "remnant_wd_mass_msun", "remnant_ns_mass_msun", "remnant_bh_mass_fraction",
            "wd_luminosity_lsun", "ns_luminosity_lsun", "bh_luminosity_lsun",
            "cc_yield", "galaxy_inflow_msun_yr", "mass_to_light_ratio",
            "bh_eddington_ratio_high", "bh_eddington_ratio_active",
            "bh_eddington_ratio_low", "bh_fuel_gas_fraction_per_gyr",
            "agn_fuel_active_threshold", "agn_fuel_inactive_threshold",
            "agn_hysteresis_margin", "cluster_accretion_msun_yr",
            "void_volume_fraction_max",
        ):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0:
                raise EvolutionValidationError(f"BuiltinModelParams.{name} must be >= 0")
        if not (0.0 <= self.stellar_return_fraction <= 1.0):
            raise EvolutionValidationError("stellar_return_fraction must be in [0, 1]")
        if not isinstance(self.population_bins, int) or self.population_bins < 2:
            raise EvolutionValidationError("population_bins must be an int >= 2")
        if not isinstance(self.max_cohorts_per_bin, int) or self.max_cohorts_per_bin < 2:
            raise EvolutionValidationError("max_cohorts_per_bin must be an int >= 2")

    def __post_init__(self):
        self.validate()
        if self.agn_fuel_inactive_threshold > self.agn_fuel_active_threshold:
            raise EvolutionValidationError(
                "agn_fuel_inactive_threshold must be <= agn_fuel_active_threshold"
            )
        if self.void_volume_fraction_max > 1.0:
            raise EvolutionValidationError("void_volume_fraction_max must be <= 1")


# ==========================================================================
# Shared astrophysical relations (documented power-law approximations)
# ==========================================================================
def main_sequence_lifetime_gyr(mass_msun: float, p: BuiltinModelParams) -> float:
    """t_MS = t_MS_sun * (M/Msun)^(-alpha). Order-of-magnitude relation."""
    m = require_finite_number(mass_msun, "mass_msun")
    if m <= 0.0:
        raise EvolutionValidationError("stellar mass must be > 0")
    return p.t_ms_sun_gyr * (m ** (-p.ml_alpha))


def main_sequence_luminosity_lsun(mass_msun: float, p: BuiltinModelParams) -> float:
    """L = (M/Msun)^beta. Order-of-magnitude mass-luminosity relation."""
    m = require_finite_number(mass_msun, "mass_msun")
    if m <= 0.0:
        raise EvolutionValidationError("stellar mass must be > 0")
    return m ** p.ml_beta


def remnant_for_mass(mass_msun: float, p: BuiltinModelParams) -> RemnantKind:
    if mass_msun >= p.m_bh_threshold_msun:
        return RemnantKind.STELLAR_MASS_BLACK_HOLE
    if mass_msun >= p.m_ns_threshold_msun:
        return RemnantKind.NEUTRON_STAR
    return RemnantKind.WHITE_DWARF


def remnant_mass_msun(progenitor_msun: float, p: BuiltinModelParams) -> float:
    kind = remnant_for_mass(progenitor_msun, p)
    if kind is RemnantKind.STELLAR_MASS_BLACK_HOLE:
        return progenitor_msun * p.remnant_bh_mass_fraction
    if kind is RemnantKind.NEUTRON_STAR:
        return p.remnant_ns_mass_msun
    return min(p.remnant_wd_mass_msun, progenitor_msun)


def classification_provenance(classification: ModelClassification) -> DataProvenance:
    """Mapping from model classification to the provenance of its outputs."""
    if classification is ModelClassification.SPECULATIVE:
        return DataProvenance.SPECULATIVE_MODEL
    if classification in (ModelClassification.THEORETICAL, ModelClassification.HYPOTHETICAL):
        return DataProvenance.THEORETICAL_MODEL
    return DataProvenance.SIMULATED_DATA


def _params_of(model: EvolutionModel) -> BuiltinModelParams:
    """Reconstruct the parameter block from a model's parameter Quantities.

    Model parameters live in the registry entry, so steps stay pure
    functions of (state, dt, effective model) and scenario overrides flow
    through the engine's effective-model construction.
    """
    q = model.parameters
    return BuiltinModelParams(
        t_ms_sun_gyr=q["t_ms_sun_gyr"].value,
        ml_alpha=q["ml_alpha"].value,
        ml_beta=q["ml_beta"].value,
        post_ms_fraction=q["post_ms_fraction"].value,
        post_ms_luminosity_boost=q["post_ms_luminosity_boost"].value,
        m_ns_threshold_msun=q["m_ns_threshold_msun"].value,
        m_bh_threshold_msun=q["m_bh_threshold_msun"].value,
        remnant_wd_mass_msun=q["remnant_wd_mass_msun"].value,
        remnant_ns_mass_msun=q["remnant_ns_mass_msun"].value,
        remnant_bh_mass_fraction=q["remnant_bh_mass_fraction"].value,
        wd_luminosity_lsun=q["wd_luminosity_lsun"].value,
        ns_luminosity_lsun=q["ns_luminosity_lsun"].value,
        bh_luminosity_lsun=q["bh_luminosity_lsun"].value,
        imf_alpha_low=q["imf_alpha_low"].value,
        imf_alpha_high=q["imf_alpha_high"].value,
        imf_break_msun=q["imf_break_msun"].value,
        imf_min_mass_msun=q["imf_min_mass_msun"].value,
        imf_max_mass_msun=q["imf_max_mass_msun"].value,
        population_bins=int(q["population_bins"].value),
        cohort_death_window_gyr=q["cohort_death_window_gyr"].value,
        max_cohorts_per_bin=int(q["max_cohorts_per_bin"].value),
        cc_yield=q["cc_yield"].value,
        sn_number_proxy_progenitor_msun=q["sn_number_proxy_progenitor_msun"].value,
        gas_depletion_time_gyr=q["gas_depletion_time_gyr"].value,
        stellar_return_time_gyr=q["stellar_return_time_gyr"].value,
        stellar_return_fraction=q["stellar_return_fraction"].value,
        galaxy_inflow_msun_yr=q["galaxy_inflow_msun_yr"].value,
        mass_to_light_ratio=q["mass_to_light_ratio"].value,
        bh_salpeter_time_gyr=q["bh_salpeter_time_gyr"].value,
        bh_eddington_ratio_high=q["bh_eddington_ratio_high"].value,
        bh_eddington_ratio_active=q["bh_eddington_ratio_active"].value,
        bh_eddington_ratio_low=q["bh_eddington_ratio_low"].value,
        bh_fuel_gas_fraction_per_gyr=q["bh_fuel_gas_fraction_per_gyr"].value,
        agn_fuel_active_threshold=q["agn_fuel_active_threshold"].value,
        agn_fuel_inactive_threshold=q["agn_fuel_inactive_threshold"].value,
        agn_hysteresis_margin=q["agn_hysteresis_margin"].value,
        morphology_relaxation_gyr=q["morphology_relaxation_gyr"].value,
        cluster_accretion_msun_yr=q["cluster_accretion_msun_yr"].value,
        web_growth_rate_per_gyr=q["web_growth_rate_per_gyr"].value,
        web_decay_rate_per_gyr=q["web_decay_rate_per_gyr"].value,
        web_transfer_rate_per_gyr=q["web_transfer_rate_per_gyr"].value,
        void_volume_growth_per_gyr=q["void_volume_growth_per_gyr"].value,
        void_volume_fraction_max=q["void_volume_fraction_max"].value,
        connectivity_decay_per_gyr=q["connectivity_decay_per_gyr"].value,
        connectivity_growth_per_gyr=q["connectivity_growth_per_gyr"].value,
    )


def _builtin_parameter_quantities(p: BuiltinModelParams) -> Dict[str, Quantity]:
    """Parameter block as registry Quantities (documentation + overrides)."""
    out: Dict[str, Quantity] = {}
    for name in (
        "t_ms_sun_gyr", "ml_alpha", "ml_beta", "post_ms_fraction",
        "post_ms_luminosity_boost", "m_ns_threshold_msun", "m_bh_threshold_msun",
        "remnant_wd_mass_msun", "remnant_ns_mass_msun", "remnant_bh_mass_fraction",
        "wd_luminosity_lsun", "ns_luminosity_lsun", "bh_luminosity_lsun",
        "imf_alpha_low", "imf_alpha_high", "imf_break_msun",
        "imf_min_mass_msun", "imf_max_mass_msun", "cohort_death_window_gyr",
        "cc_yield", "sn_number_proxy_progenitor_msun",
        "gas_depletion_time_gyr", "stellar_return_time_gyr",
        "stellar_return_fraction", "galaxy_inflow_msun_yr",
        "mass_to_light_ratio", "bh_salpeter_time_gyr",
        "bh_eddington_ratio_high", "bh_eddington_ratio_active",
        "bh_eddington_ratio_low", "bh_fuel_gas_fraction_per_gyr",
        "agn_fuel_active_threshold", "agn_fuel_inactive_threshold",
        "agn_hysteresis_margin", "morphology_relaxation_gyr",
        "cluster_accretion_msun_yr", "web_growth_rate_per_gyr",
        "web_decay_rate_per_gyr", "web_transfer_rate_per_gyr",
        "void_volume_growth_per_gyr", "void_volume_fraction_max",
        "connectivity_decay_per_gyr", "connectivity_growth_per_gyr",
    ):
        out[name] = _q(getattr(p, name), "dimensionless", f"builtin parameter {name}")
    out["population_bins"] = _q(float(p.population_bins), "count", "conveyor mass-bin count")
    out["max_cohorts_per_bin"] = _q(float(p.max_cohorts_per_bin), "count", "cohort coarsening budget per bin")
    return out


# ==========================================================================
# 1. Single-star lifecycle model
# ==========================================================================
STELLAR_MODEL_ID = "stellar.single_star_lifecycle.v1"


def _stellar_rate_scale(state: EvolutionState, model: EvolutionModel) -> float:
    """Adaptive-stepping rate: inverse time to the next lifecycle boundary.

    Steps shrink as a transition approaches (documented adaptive policy);
    far from any boundary the rate is 0 (no information) and the policy
    ceiling applies. Parameters come from the effective model (including
    scenario overrides) — never from state metadata.
    """
    p = _params_of(model)
    m0 = state.quantity_value("initial_mass_msun")
    age = state.quantity_value("age_gyr", 0.0)
    if m0 is None or m0 <= 0.0:
        return 0.0
    if state.phase == "REMNANT":
        return 0.0
    t_ms = main_sequence_lifetime_gyr(m0, p)
    if state.phase == "POST_MAIN_SEQUENCE":
        t_next = t_ms * (1.0 + p.post_ms_fraction) - age
    else:
        t_next = t_ms - age
    if t_next <= 0.0:
        return 0.0
    return 1.0 / t_next


def _stellar_step(state: EvolutionState, dt_gyr: float, model: EvolutionModel) -> EvolutionState:
    if state.object_kind != KIND_STAR:
        raise EvolutionLimitationError(
            LimitationState.INCOMPATIBLE_MODEL,
            f"stellar lifecycle model requires a {KIND_STAR} state, got {state.object_kind}",
        )
    p = _params_of(model)
    m0 = state.quantity_value("initial_mass_msun")
    if m0 is None or m0 <= 0.0:
        raise EvolutionLimitationError(
            LimitationState.MISSING_REQUIRED_DATA,
            "stellar lifecycle requires quantity 'initial_mass_msun' > 0",
        )
    age = state.quantity_value("age_gyr", 0.0)
    new_age = age + dt_gyr

    t_ms = main_sequence_lifetime_gyr(m0, p)
    t_end = t_ms * (1.0 + p.post_ms_fraction)

    phase = state.phase
    if phase == "FORMATION":
        phase = "MAIN_SEQUENCE"

    metadata = dict(state.metadata)
    updates: Dict[str, Quantity] = {"age_gyr": _q(new_age, "Gyr", "time since formation")}

    if phase == "MAIN_SEQUENCE":
        if new_age >= t_ms:
            phase = "POST_MAIN_SEQUENCE"
            metadata["transition_detail"] = (
                f"exhausted core hydrogen at t_MS ~ {t_ms:.6g} Gyr "
                "(power-law mass-lifetime relation)"
            )
        lum = main_sequence_luminosity_lsun(m0, p)
        updates["luminosity_lsun"] = _q(
            lum, "Lsun", "mass-luminosity power law; constant on the MS in this model"
        )
        updates["mass_msun"] = _q(m0, "Msun", "no mass loss modeled (documented limitation)")
    elif phase == "POST_MAIN_SEQUENCE":
        if new_age < t_end:
            lum = main_sequence_luminosity_lsun(m0, p) * p.post_ms_luminosity_boost
            updates["luminosity_lsun"] = _q(
                lum,
                "Lsun",
                "MS luminosity x configurable post-MS boost factor "
                "(uncertain at order-of-magnitude level)",
            )
            updates["mass_msun"] = _q(m0, "Msun", "no mass loss modeled (documented limitation)")
        else:
            kind = remnant_for_mass(m0, p)
            r_mass = remnant_mass_msun(m0, p)
            phase = "REMNANT"
            metadata["remnant_kind"] = kind.value
            metadata["progenitor_initial_mass_msun"] = m0
            r_lum = {
                RemnantKind.WHITE_DWARF.value: p.wd_luminosity_lsun,
                RemnantKind.NEUTRON_STAR.value: p.ns_luminosity_lsun,
                RemnantKind.STELLAR_MASS_BLACK_HOLE.value: p.bh_luminosity_lsun,
            }[kind.value]
            updates["mass_msun"] = _q(r_mass, "Msun", f"reduced-order {kind.value} mass assignment")
            updates["luminosity_lsun"] = _q(
                r_lum,
                "Lsun",
                f"order-of-magnitude {kind.value} luminosity (no cooling curve modeled)",
            )
            metadata["transition_detail"] = (
                f"terminal-age transition at t ~ {t_end:.6g} Gyr; "
                f"{kind.value} remnant of ~{r_mass:.3g} Msun"
            )
    else:  # REMNANT: no further evolution in this model
        if "mass_msun" in state.quantities:
            updates.setdefault("mass_msun", state.quantities["mass_msun"])
        if "luminosity_lsun" in state.quantities:
            updates.setdefault("luminosity_lsun", state.quantities["luminosity_lsun"])

    return replace(
        state,
        cosmic_time_gyr=state.cosmic_time_gyr + dt_gyr,
        phase=phase,
        quantities={**state.quantities, **updates},
        metadata=metadata,
    )


def make_star_state(
    object_id: str,
    cosmic_time_gyr: float,
    initial_mass_msun: float,
    *,
    age_gyr: float = 0.0,
    scenario=None,
    params: Optional[BuiltinModelParams] = None,
) -> EvolutionState:
    """Factory for a STAR-kind evolution state near the start of its life."""
    p = params or BuiltinModelParams()
    provenance = scenario.provenance if scenario is not None else DataProvenance.SIMULATED_DATA
    projection = scenario.projection_class if scenario is not None else ProjectionClass.NONE
    phase = "MAIN_SEQUENCE" if age_gyr > 0.0 else "FORMATION"
    return EvolutionState(
        object_id=object_id,
        object_kind=KIND_STAR,
        cosmic_time_gyr=cosmic_time_gyr,
        phase=phase,
        quantities={
            "initial_mass_msun": _q(initial_mass_msun, "Msun", "zero-age main-sequence mass"),
            "mass_msun": _q(initial_mass_msun, "Msun", "current mass (no mass loss modeled)"),
            "age_gyr": _q(age_gyr, "Gyr"),
            "luminosity_lsun": _q(
                main_sequence_luminosity_lsun(initial_mass_msun, p),
                "Lsun",
                "mass-luminosity power law",
            ),
        },
        model_id=STELLAR_MODEL_ID,
        provenance=provenance,
        projection_class=projection,
        metadata={},
    )


# ==========================================================================
# 2. Population conveyor model
# ==========================================================================
POPULATION_MODEL_ID = "population.conveyor.v1"


def _bin_edges(p: BuiltinModelParams) -> List[float]:
    lo = math.log10(p.imf_min_mass_msun)
    hi = math.log10(p.imf_max_mass_msun)
    step = (hi - lo) / p.population_bins
    return [10.0 ** (lo + i * step) for i in range(p.population_bins + 1)]


def _bin_centres(p: BuiltinModelParams) -> List[float]:
    edges = _bin_edges(p)
    return [math.sqrt(edges[i] * edges[i + 1]) for i in range(p.population_bins)]


def _imf_mass_fractions(p: BuiltinModelParams) -> List[float]:
    """Deterministic newborn-mass distribution over the bins.

    Exact integral of the two-slope power-law IMF: the mass fraction in a
    bin is the integral of m*(dN/dm) over the bin divided by the total.
    Bins straddling the IMF break are classified by their geometric-midpoint
    mass (documented: break-placement error bounded by the bin width).
    """
    edges = _bin_edges(p)

    def _mass_integral(a: float, b: float, alpha: float) -> float:
        exponent = 2.0 - alpha
        if abs(exponent) < 1.0e-12:
            return math.log(b / a)
        return (b ** exponent - a ** exponent) / exponent

    parts: List[float] = []
    for i in range(p.population_bins):
        a, b = edges[i], edges[i + 1]
        mid = math.sqrt(a * b)
        alpha = p.imf_alpha_low if mid <= p.imf_break_msun else p.imf_alpha_high
        parts.append(_mass_integral(a, b, alpha))
    total = sum(parts)
    return [w / total for w in parts]


def _population_rate_scale(state: EvolutionState, model: EvolutionModel) -> float:
    """Adaptive rate: specific star formation (1/Gyr). Declining SFR lets
    steps lengthen toward the policy ceiling; the floor guards against
    division by ~0."""
    sfr = state.quantity_value("sfr_msun_yr")
    live = state.quantity_value("live_stellar_mass_msun")
    if sfr is None or live is None or live <= 0.0:
        return 0.0
    return (sfr * 1.0e9) / live  # 1/Gyr


def _population_step(state: EvolutionState, dt_gyr: float, model: EvolutionModel) -> EvolutionState:
    if state.object_kind != KIND_POPULATION:
        raise EvolutionLimitationError(
            LimitationState.INCOMPATIBLE_MODEL,
            f"population conveyor requires a {KIND_POPULATION} state, got {state.object_kind}",
        )
    p = _params_of(model)
    edges = _bin_edges(p)
    centres = _bin_centres(p)
    fractions = _imf_mass_fractions(p)
    n_bins = p.population_bins
    t_ms_by_bin = [main_sequence_lifetime_gyr(c, p) for c in centres]

    gas = state.quantity_value("gas_mass_msun", 0.0)
    metal = state.quantity_value("metal_mass_msun", 0.0)
    wd = state.quantity_value("remnant_wd_msun", 0.0)
    ns = state.quantity_value("remnant_ns_msun", 0.0)
    bh = state.quantity_value("remnant_bh_msun", 0.0)
    sfr_requested = state.metadata.get("sfr_requested_msun_yr")
    if sfr_requested is None:
        sfr_requested = state.quantity_value("sfr_msun_yr", 0.0)
    sfr_requested = float(sfr_requested)
    age = state.quantity_value("age_gyr", 0.0)

    cohorts_raw: List[List[float]] = [
        [float(c[0]), float(c[1]), float(c[2])] for c in state.metadata.get("cohorts", [])
    ]  # entries: [bin_index, birth_gyr, mass_msun]
    now = state.cosmic_time_gyr

    # ---- 1. delayed stellar deaths (smooth turnoff window per bin) ------
    dead_total = 0.0
    dead_cc = 0.0
    formed_wd = formed_ns = formed_bh = 0.0
    returned_gas = 0.0
    w = p.cohort_death_window_gyr
    survivors: List[List[float]] = []
    for bin_index, birth, mass in cohorts_raw:
        i = int(bin_index)
        f0 = min(max((now - birth - t_ms_by_bin[i]) / w, 0.0), 1.0)
        f1 = min(max((now + dt_gyr - birth - t_ms_by_bin[i]) / w, 0.0), 1.0)
        died = mass * (f1 - f0)
        alive = mass - died
        if died > 0.0:
            m_mid = centres[i]
            remnant = remnant_for_mass(m_mid, p)
            if remnant is RemnantKind.WHITE_DWARF:
                r_frac = p.remnant_wd_mass_msun / max(m_mid, 1.0e-9)
                formed_wd += died * min(r_frac, 1.0)
            elif remnant is RemnantKind.NEUTRON_STAR:
                formed_ns += died * min(p.remnant_ns_mass_msun / m_mid, 1.0)
            else:
                formed_bh += died * p.remnant_bh_mass_fraction
            dead_total += died
            if m_mid >= p.m_ns_threshold_msun:
                dead_cc += died
        if alive > _NUMERICAL_MASS_FLOOR_MSUN:
            survivors.append([i, birth, alive])
    # mass returned to the gas reservoir = died - locked-in remnants
    locked = formed_wd + formed_ns + formed_bh
    returned_gas = max(dead_total - locked, 0.0)
    cohorts_raw = survivors

    gas += returned_gas
    z_current = (metal / gas) if gas > _NUMERICAL_MASS_FLOOR_MSUN else 0.0
    metal += p.cc_yield * dead_cc + z_current * returned_gas

    # ---- 2. star formation (gas-limited; requested driver preserved) -----
    # The REQUESTED SFR is an external driver held in metadata: gas-limiting
    # the actual rate must not ratchet the driver down (a temporary gas
    # shortage would otherwise quench the population forever).
    dt_yr = dt_gyr * 1.0e9
    new_stars = min(sfr_requested * dt_yr, gas)
    sfr_effective = (new_stars / dt_yr) if dt_yr > 0.0 else 0.0
    metal_consumed = z_current * new_stars
    gas -= new_stars
    metal = max(metal - metal_consumed, 0.0)
    if new_stars > 0.0:
        birth_time = now + 0.5 * dt_gyr
        for i, frac in enumerate(fractions):
            m_i = new_stars * frac
            if m_i > 0.0:
                cohorts_raw.append([i, birth_time, m_i])

    # ---- 3. deterministic cohort coarsening (budget-driven) --------------
    coarsened = 0
    by_bin: Dict[int, List[List[float]]] = {}
    for c in cohorts_raw:
        by_bin.setdefault(int(c[0]), []).append(c)
    max_cohorts = p.max_cohorts_per_bin
    for bin_index in sorted(by_bin.keys()):
        group = sorted(by_bin[bin_index], key=lambda c: (c[1], c[2]))
        while len(group) > max_cohorts:
            a, b = group[0], group[1]
            mass_ab = a[2] + b[2]
            weighted_birth = (a[1] * a[2] + b[1] * b[2]) / mass_ab if mass_ab > 0 else a[1]
            group = [[bin_index, weighted_birth, mass_ab]] + group[2:]
            coarsened += 1
        by_bin[bin_index] = group
    cohorts_raw = [c for k in sorted(by_bin.keys()) for c in by_bin[k]]

    # ---- 4. bookkeeping ---------------------------------------------------
    live_new = sum(c[2] for c in cohorts_raw)
    wd_new = wd + formed_wd
    ns_new = ns + formed_ns
    bh_new = bh + formed_bh
    z_new = (metal / gas) if gas > _NUMERICAL_MASS_FLOOR_MSUN else 0.0
    lum = 0.0
    for bin_index, birth, mass in cohorts_raw:
        m_mid = centres[int(bin_index)]
        lum += mass * (main_sequence_luminosity_lsun(m_mid, p) / m_mid)

    mass_function = [
        [centres[i], sum(c[2] for c in by_bin.get(i, []))] for i in range(n_bins)
    ]
    age_distribution: Dict[float, float] = {}
    for bin_index, birth, mass in cohorts_raw:
        key = round(now + dt_gyr - birth, 9)
        age_distribution[key] = age_distribution.get(key, 0.0) + mass

    metadata = dict(state.metadata)
    metadata["cohorts"] = cohorts_raw
    metadata["mass_function"] = mass_function
    metadata["age_distribution"] = sorted(age_distribution.items())
    metadata.setdefault("parent_object_id", "")
    metadata["sfr_requested_msun_yr"] = sfr_requested
    if coarsened:
        metadata["coarsened_cohorts"] = int(metadata.get("coarsened_cohorts", 0)) + coarsened
    if sfr_requested > 0.0 and sfr_effective == 0.0:
        metadata["transition_detail"] = "gas reservoir exhausted; star formation ceased"

    updates = {
        "live_stellar_mass_msun": _q(live_new, "Msun"),
        "gas_mass_msun": _q(gas, "Msun"),
        "metal_mass_msun": _q(metal, "Msun"),
        "metallicity_z": _q(z_new, "dimensionless", "closed-box gas metallicity"),
        "remnant_wd_msun": _q(wd_new, "Msun"),
        "remnant_ns_msun": _q(ns_new, "Msun"),
        "remnant_bh_msun": _q(bh_new, "Msun"),
        "sfr_msun_yr": _q(sfr_effective, "Msun/yr"),
        "birth_rate_msun_yr": _q(new_stars / dt_yr if dt_yr > 0.0 else 0.0, "Msun/yr"),
        "death_rate_msun_yr": _q(dead_total / dt_yr if dt_yr > 0.0 else 0.0, "Msun/yr"),
        "sn_mass_rate_msun_yr": _q(dead_cc / dt_yr if dt_yr > 0.0 else 0.0, "Msun/yr"),
        "sn_number_proxy_per_gyr": _q(
            dead_cc / p.sn_number_proxy_progenitor_msun / dt_gyr if dt_gyr > 0.0 else 0.0,
            "1/Gyr",
            "ORDER-OF-MAGNITUDE core-collapse count proxy: dying CC mass divided "
            "by an assumed average progenitor mass; not an event count",
        ),
        "luminosity_lsun": _q(
            lum,
            "Lsun",
            "main-sequence mass-luminosity sum; post-MS light not cohort-resolved "
            "(documented approximation)",
        ),
        "age_gyr": _q(age + dt_gyr, "Gyr"),
    }
    return replace(
        state,
        cosmic_time_gyr=now + dt_gyr,
        phase="FORMING" if sfr_effective > 0.0 else "QUIESCENT",
        quantities={**state.quantities, **updates},
        metadata=metadata,
    )


def make_population_state(
    population_id: str,
    cosmic_time_gyr: float,
    *,
    gas_mass_msun: float,
    sfr_msun_yr: float = 0.0,
    metallicity_z: float = 0.0,
    parent_object_id: str = "",
    scenario=None,
    params: Optional[BuiltinModelParams] = None,
) -> EvolutionState:
    """Factory for a POPULATION-kind evolution state."""
    p = params or BuiltinModelParams()
    p.validate()
    provenance = scenario.provenance if scenario is not None else DataProvenance.SIMULATED_DATA
    projection = scenario.projection_class if scenario is not None else ProjectionClass.NONE
    metal = max(metallicity_z, 0.0) * max(gas_mass_msun, 0.0)
    return EvolutionState(
        object_id=population_id,
        object_kind=KIND_POPULATION,
        cosmic_time_gyr=cosmic_time_gyr,
        phase="FORMING" if sfr_msun_yr > 0.0 else "QUIESCENT",
        quantities={
            "live_stellar_mass_msun": _q(0.0, "Msun"),
            "gas_mass_msun": _q(gas_mass_msun, "Msun"),
            "metal_mass_msun": _q(metal, "Msun"),
            "metallicity_z": _q(max(metallicity_z, 0.0), "dimensionless", "initial gas metallicity"),
            "remnant_wd_msun": _q(0.0, "Msun"),
            "remnant_ns_msun": _q(0.0, "Msun"),
            "remnant_bh_msun": _q(0.0, "Msun"),
            "sfr_msun_yr": _q(sfr_msun_yr, "Msun/yr"),
            "birth_rate_msun_yr": _q(0.0, "Msun/yr"),
            "death_rate_msun_yr": _q(0.0, "Msun/yr"),
            "sn_mass_rate_msun_yr": _q(0.0, "Msun/yr"),
            "sn_number_proxy_per_gyr": _q(0.0, "1/Gyr", "order-of-magnitude CC count proxy"),
            "luminosity_lsun": _q(0.0, "Lsun"),
            "age_gyr": _q(0.0, "Gyr"),
        },
        model_id=POPULATION_MODEL_ID,
        provenance=provenance,
        projection_class=projection,
        metadata={
            "cohorts": [],
            "mass_function": [],
            "age_distribution": [],
            "parent_object_id": parent_object_id,
            "coarsened_cohorts": 0,
            "sfr_requested_msun_yr": max(sfr_msun_yr, 0.0),
        },
    )


# ==========================================================================
# 3. Galaxy one-zone model
# ==========================================================================
GALAXY_MODEL_ID = "galaxy.one_zone.v1"

# Reduced-order morphology tendency anchors: living-gas fraction -> target
# morphology distribution (piecewise-linear in each class). These are model
# PARAMETERS (configurable via BuiltinModelParams consumers via metadata)
# expressing a qualitative tendency, not measured transition probabilities.
_MORPH_ANCHORS: Tuple[Tuple[float, Dict[str, float]], ...] = (
    (0.50, {"SPIRAL": 0.70, "LENTICULAR": 0.10, "ELLIPTICAL": 0.05, "IRREGULAR": 0.10, "INTERACTING": 0.05}),
    (0.10, {"SPIRAL": 0.45, "LENTICULAR": 0.30, "ELLIPTICAL": 0.15, "IRREGULAR": 0.05, "INTERACTING": 0.05}),
    (0.02, {"SPIRAL": 0.20, "LENTICULAR": 0.35, "ELLIPTICAL": 0.40, "IRREGULAR": 0.00, "INTERACTING": 0.05}),
    (0.00, {"SPIRAL": 0.05, "LENTICULAR": 0.25, "ELLIPTICAL": 0.70, "IRREGULAR": 0.00, "INTERACTING": 0.00}),
)
_MORPH_CLASSES = tuple(m.value for m in MorphologyClass)

_AGN_RATES = {
    AGNActivityState.HIGH_ACTIVITY.value: "bh_eddington_ratio_high",
    AGNActivityState.ACTIVE.value: "bh_eddington_ratio_active",
    AGNActivityState.LOW_ACTIVITY.value: "bh_eddington_ratio_low",
    AGNActivityState.INACTIVE.value: None,
}


def _galaxy_rate_scale(state: EvolutionState, model: EvolutionModel) -> float:
    """Adaptive rate: specific SFR + BH specific growth (1/Gyr)."""
    sfr = state.quantity_value("sfr_msun_yr")
    stellar = state.quantity_value("stellar_mass_msun")
    bh = state.quantity_value("bh_mass_msun")
    rate = 0.0
    if sfr is not None and stellar is not None and stellar > 0.0:
        rate += (sfr * 1.0e9) / stellar
    if bh is not None and bh > 0.0 and state.phase != AGNActivityState.INACTIVE.value:
        # BH growth is capped by the fuel term; the SFR term dominates the
        # clock. (Fuel-capped growth is at most 1e-3/Gyr by default.)
        rate += 1.0e-3
    return rate


def _morph_target(f_gas: float) -> Dict[str, float]:
    anchors = _MORPH_ANCHORS
    if f_gas >= anchors[0][0]:
        lo, hi = anchors[0], anchors[0]
    else:
        lo, hi = anchors[-2], anchors[-1]
        for i in range(len(anchors) - 1):
            if anchors[i][0] >= f_gas >= anchors[i + 1][0]:
                lo, hi = anchors[i], anchors[i + 1]
                break
    span = lo[0] - hi[0]
    if span <= 0.0:
        return dict(hi[1])
    t = (lo[0] - f_gas) / span
    return {
        cls: lo[1][cls] + t * (hi[1][cls] - lo[1][cls]) for cls in _MORPH_CLASSES
    }


def _next_agn_state(previous: str, f_gas: float, p: BuiltinModelParams) -> AGNActivityState:
    """Hysteresis state machine (documented): staying active requires only
    the active threshold; igniting from quiescence needs active + margin."""
    was_active = previous in (AGNActivityState.ACTIVE.value, AGNActivityState.HIGH_ACTIVITY.value)
    threshold = p.agn_fuel_active_threshold + (0.0 if was_active else p.agn_hysteresis_margin)
    if f_gas >= threshold:
        return AGNActivityState.HIGH_ACTIVITY if f_gas >= 2.0 * p.agn_fuel_active_threshold else AGNActivityState.ACTIVE
    if f_gas >= p.agn_fuel_inactive_threshold:
        return AGNActivityState.LOW_ACTIVITY if was_active else AGNActivityState.INACTIVE
    return AGNActivityState.INACTIVE


def _galaxy_step(state: EvolutionState, dt_gyr: float, model: EvolutionModel) -> EvolutionState:
    if state.object_kind != KIND_GALAXY:
        raise EvolutionLimitationError(
            LimitationState.INCOMPATIBLE_MODEL,
            f"galaxy one-zone model requires a {KIND_GALAXY} state, got {state.object_kind}",
        )
    p = _params_of(model)
    stellar = state.quantity_value("stellar_mass_msun", 0.0)
    gas = state.quantity_value("gas_mass_msun", 0.0)
    metal = state.quantity_value("metal_mass_msun", 0.0)
    bh = state.quantity_value("bh_mass_msun", 0.0)
    remnants = state.quantity_value("remnant_mass_msun", 0.0)
    age = state.quantity_value("age_gyr", 0.0)
    now = state.cosmic_time_gyr

    # ---- gas flows ---------------------------------------------------------
    gas += p.galaxy_inflow_msun_yr * dt_gyr * 1.0e9  # Msun/yr x yr -> Msun
    sfr_prev = state.quantity_value("sfr_msun_yr", 0.0)
    z_current = (metal / gas) if gas > _NUMERICAL_MASS_FLOOR_MSUN else 0.0

    # ---- star formation + delayed recycling --------------------------------
    new_stars = min((gas / p.gas_depletion_time_gyr) * dt_gyr, gas)
    sfr_effective = new_stars / dt_gyr if dt_gyr > 0.0 else 0.0
    deaths = (stellar / p.stellar_return_time_gyr) * dt_gyr
    deaths = min(deaths, stellar)
    returned = deaths * p.stellar_return_fraction
    locked = deaths - returned  # mass locked in new remnants (tracked, not lost)
    stellar = stellar - deaths + new_stars
    gas = gas - new_stars + returned
    remnants += locked
    metal += p.cc_yield * deaths + z_current * returned - z_current * new_stars

    # ---- SMBH growth + AGN activity state ----------------------------------
    f_gas = gas / (gas + stellar) if (gas + stellar) > 0.0 else 0.0
    agn = _next_agn_state(state.phase, f_gas, p)
    ratio_key = _AGN_RATES.get(agn.value)
    d_bh = 0.0
    if ratio_key is not None:
        ratio = getattr(p, ratio_key)
        d_bh = bh * (ratio / p.bh_salpeter_time_gyr) * dt_gyr
        fuel_cap = p.bh_fuel_gas_fraction_per_gyr * gas * dt_gyr
        d_bh = min(d_bh, fuel_cap)
        bh += d_bh
        gas = max(gas - d_bh, 0.0)

    # ---- morphology distribution drift --------------------------------------
    morph_raw = state.metadata.get(
        "morphology",
        {cls: 1.0 / len(_MORPH_CLASSES) for cls in _MORPH_CLASSES},
    )
    morph = {cls: float(morph_raw.get(cls, 0.0)) for cls in _MORPH_CLASSES}
    total_p = sum(morph.values())
    if total_p <= 0.0:
        morph = {cls: 1.0 / len(_MORPH_CLASSES) for cls in _MORPH_CLASSES}
    else:
        morph = {cls: v / total_p for cls, v in morph.items()}
    target = _morph_target(f_gas)
    tau = p.morphology_relaxation_gyr
    blend = min(dt_gyr / tau, 1.0)
    morph = {cls: morph[cls] + blend * (target[cls] - morph[cls]) for cls in _MORPH_CLASSES}
    total_p = sum(morph.values())
    morph = {cls: v / total_p for cls, v in morph.items()}

    z_new = (metal / gas) if gas > _NUMERICAL_MASS_FLOOR_MSUN else 0.0
    luminosity = stellar / max(p.mass_to_light_ratio, 1.0e-9)

    metadata = dict(state.metadata)
    metadata["morphology"] = morph
    if new_stars > 0.0 and sfr_prev > 0.0 and sfr_effective == 0.0:
        metadata["transition_detail"] = "gas reservoir exhausted; star formation ceased"
    elif state.phase != agn.value:
        metadata["transition_detail"] = (
            f"AGN activity {state.phase} -> {agn.value} at gas fraction {f_gas:.4g} "
            "(hysteresis state machine)"
        )

    updates = {
        "stellar_mass_msun": _q(stellar, "Msun"),
        "gas_mass_msun": _q(gas, "Msun"),
        "metal_mass_msun": _q(metal, "Msun"),
        "metallicity_z": _q(z_new, "dimensionless", "closed-box gas metallicity"),
        "sfr_msun_yr": _q(sfr_effective * _MSUN_PER_GYR_TO_MSUN_YR, "Msun/yr"),
        "bh_mass_msun": _q(bh, "Msun", "population-level SMBH mass (reduced-order growth)"),
        "remnant_mass_msun": _q(remnants, "Msun", "locked stellar remnants (deaths minus returned mass)"),
        "luminosity_lsun": _q(
            luminosity, "Lsun", "stellar mass / configured mass-to-light ratio (crude proxy)"
        ),
        "age_gyr": _q(age + dt_gyr, "Gyr"),
    }
    return replace(
        state,
        cosmic_time_gyr=now + dt_gyr,
        phase=agn.value,
        quantities={**state.quantities, **updates},
        metadata=metadata,
    )


def make_galaxy_state(
    galaxy_id: str,
    cosmic_time_gyr: float,
    *,
    stellar_mass_msun: float,
    gas_mass_msun: float,
    bh_mass_msun: float = 0.0,
    metallicity_z: float = 0.0,
    scenario=None,
    params: Optional[BuiltinModelParams] = None,
) -> EvolutionState:
    """Factory for a GALAXY-kind evolution state (one-zone reduced order)."""
    p = params or BuiltinModelParams()
    p.validate()
    provenance = scenario.provenance if scenario is not None else DataProvenance.SIMULATED_DATA
    projection = scenario.projection_class if scenario is not None else ProjectionClass.NONE
    f_gas = gas_mass_msun / max(gas_mass_msun + stellar_mass_msun, 1.0e-30)
    agn = _next_agn_state(AGNActivityState.INACTIVE.value, f_gas, p)
    morph = {cls: 1.0 / len(_MORPH_CLASSES) for cls in _MORPH_CLASSES}
    return EvolutionState(
        object_id=galaxy_id,
        object_kind=KIND_GALAXY,
        cosmic_time_gyr=cosmic_time_gyr,
        phase=agn.value,
        quantities={
            "stellar_mass_msun": _q(stellar_mass_msun, "Msun"),
            "gas_mass_msun": _q(gas_mass_msun, "Msun"),
            "metal_mass_msun": _q(max(metallicity_z, 0.0) * gas_mass_msun, "Msun"),
            "metallicity_z": _q(max(metallicity_z, 0.0), "dimensionless", "initial gas metallicity"),
            "sfr_msun_yr": _q(0.0, "Msun/yr"),
            "bh_mass_msun": _q(bh_mass_msun, "Msun", "central SMBH mass"),
            "remnant_mass_msun": _q(0.0, "Msun"),
            "luminosity_lsun": _q(
                stellar_mass_msun / max(p.mass_to_light_ratio, 1.0e-9), "Lsun"
            ),
            "age_gyr": _q(0.0, "Gyr"),
        },
        model_id=GALAXY_MODEL_ID,
        provenance=provenance,
        projection_class=projection,
        metadata={"morphology": morph},
    )


# ==========================================================================
# 4. Cluster aggregate model
# ==========================================================================
CLUSTER_MODEL_ID = "cluster.member_aggregate.v1"


def _cluster_step(state: EvolutionState, dt_gyr: float, model: EvolutionModel) -> EvolutionState:
    if state.object_kind != KIND_CLUSTER:
        raise EvolutionLimitationError(
            LimitationState.INCOMPATIBLE_MODEL,
            f"cluster aggregate model requires a {KIND_CLUSTER} state, got {state.object_kind}",
        )
    p = _params_of(model)
    total = state.quantity_value("total_mass_msun", 0.0)
    age = state.quantity_value("age_gyr", 0.0)
    accreted = p.cluster_accretion_msun_yr * dt_gyr * 1.0e9  # Msun/yr x yr
    members = state.metadata.get("member_ids", [])
    metadata = dict(state.metadata)
    regime = metadata.get("regime", StructureRegime.UNKNOWN.value)
    metadata["regime"] = regime
    updates = {
        "total_mass_msun": _q(total + accreted, "Msun", "accretion parameter x dt"),
        "member_count": _q(float(len(members)), "count"),
        "age_gyr": _q(age + dt_gyr, "Gyr"),
    }
    return replace(
        state,
        cosmic_time_gyr=state.cosmic_time_gyr + dt_gyr,
        phase=state.phase,
        quantities={**state.quantities, **updates},
        metadata=metadata,
    )


def make_cluster_state(
    cluster_id: str,
    cosmic_time_gyr: float,
    *,
    member_ids: Tuple[str, ...] = (),
    total_mass_msun: float = 0.0,
    scenario=None,
    params: Optional[BuiltinModelParams] = None,
) -> EvolutionState:
    """Factory for a CLUSTER-kind evolution state. Aggregates (stellar/gas
    mass sums) are filled in by ``CosmicEvolutionEngine.evolve_cluster``."""
    p = params or BuiltinModelParams()
    provenance = scenario.provenance if scenario is not None else DataProvenance.SIMULATED_DATA
    projection = scenario.projection_class if scenario is not None else ProjectionClass.NONE
    return EvolutionState(
        object_id=cluster_id,
        object_kind=KIND_CLUSTER,
        cosmic_time_gyr=cosmic_time_gyr,
        phase=StructureRegime.UNKNOWN.value,
        quantities={
            "total_mass_msun": _q(total_mass_msun, "Msun"),
            "stellar_mass_msun": _q(0.0, "Msun"),
            "gas_mass_msun": _q(0.0, "Msun"),
            "bh_mass_msun": _q(0.0, "Msun"),
            "sfr_msun_yr": _q(0.0, "Msun/yr"),
            "member_count": _q(float(len(member_ids)), "count"),
            "age_gyr": _q(0.0, "Gyr"),
        },
        model_id=CLUSTER_MODEL_ID,
        provenance=provenance,
        projection_class=projection,
        metadata={"member_ids": list(member_ids), "regime": StructureRegime.UNKNOWN.value},
    )


# ==========================================================================
# 5. Cosmic-web regime evolution model
# ==========================================================================
WEB_MODEL_ID = "web.regime_evolution.v1"

EXPANSION_INPUT_KEY = "expansion_scale_ratio"


def classify_structure_regime(
    *,
    binding_energy_ratio: Optional[float],
    tolerance: float = 1.0e-9,
) -> StructureRegime:
    """Classify one structure's expansion regime from caller-supplied
    dynamics (spec 2.17). ``binding_energy_ratio`` is |E_bind| divided by
    the expansion-work proxy, computed by the CALLER from real dynamics
    (e.g. astra.nbody diagnostics) plus an injected expansion provider —
    Phase 21 never derives it. Missing inputs are an explicit refusal,
    never a bound assumption."""
    if binding_energy_ratio is None:
        raise EvolutionLimitationError(
            LimitationState.MISSING_REQUIRED_DATA,
            "structure regime requires binding_energy_ratio (|E_bind| / expansion "
            "work) computed by the caller from real dynamics + an expansion provider",
        )
    r = require_finite_number(binding_energy_ratio, "binding_energy_ratio")
    if r > 1.0 + tolerance:
        return StructureRegime.GRAVITATIONALLY_BOUND
    if r >= 1.0 - tolerance:
        return StructureRegime.EXPANDING_ASSOCIATION
    return StructureRegime.DISSOLVING


def _web_rate_scale(state: EvolutionState, model: EvolutionModel) -> float:
    return 0.0  # web processes are slow; the policy ceiling governs steps


def _web_step(state: EvolutionState, dt_gyr: float, model: EvolutionModel) -> EvolutionState:
    if state.object_kind not in (KIND_COSMIC_WEB, KIND_STRUCTURE):
        raise EvolutionLimitationError(
            LimitationState.INCOMPATIBLE_MODEL,
            f"web regime model requires a {KIND_COSMIC_WEB} state, got {state.object_kind}",
        )
    a_ratio_raw = state.metadata.get(EXPANSION_INPUT_KEY)
    if a_ratio_raw is None:
        raise EvolutionDependencyError(
            "web.regime_evolution requires a per-step expansion input "
            f"(metadata key '{EXPANSION_INPUT_KEY}'); inject a UniverseEvolutionProvider "
            "or supply expansion_ratio_fn to evolve_cosmic_web. Phase 21 does not "
            "compute cosmic expansion itself."
        )
    a_ratio = require_finite_number(a_ratio_raw, EXPANSION_INPUT_KEY)
    if a_ratio <= 0.0:
        raise EvolutionLimitationError(
            LimitationState.INVALID_COSMOLOGY,
            f"expansion scale-factor ratio must be > 0, got {a_ratio}",
        )
    p = _params_of(model)

    sigma = state.quantity_value("density_contrast_sigma", 1.0)
    node = state.quantity_value("node_mass_fraction", 0.0)
    filament = state.quantity_value("filament_mass_fraction", 0.0)
    sheet = state.quantity_value("sheet_mass_fraction", 0.0)
    void_vol = state.quantity_value("void_volume_fraction", 0.0)
    void_comoving = state.quantity_value("void_size_comoving_mpc", 0.0)
    void_proper = state.quantity_value("void_size_proper_mpc", 0.0)
    connectivity = state.quantity_value("connectivity_index", 0.0)
    age = state.quantity_value("age_gyr", 0.0)

    # Proper sizes scale with the SUPPLIED ratio (bookkeeping, not physics).
    void_proper = void_comoving * a_ratio if void_proper == 0.0 else void_proper * a_ratio

    # Density-contrast growth depends on the web-level regime tag.
    web_regime = state.metadata.get("regime", StructureRegime.EXPANDING_ASSOCIATION.value)
    if web_regime == StructureRegime.GRAVITATIONALLY_BOUND.value:
        sigma *= 1.0 + p.web_growth_rate_per_gyr * dt_gyr
        connectivity += p.connectivity_growth_per_gyr * dt_gyr
    elif web_regime == StructureRegime.DISSOLVING.value:
        sigma *= max(1.0 - p.web_decay_rate_per_gyr * dt_gyr, 0.0)
        connectivity = max(connectivity - p.connectivity_decay_per_gyr * dt_gyr, 0.0)
    else:  # EXPANDING_ASSOCIATION (default): linear growth quenched
        connectivity = max(connectivity - p.connectivity_decay_per_gyr * dt_gyr, 0.0)

    # Hierarchical inflow: sheets feed filaments feed nodes (reduced-order
    # qualitative trend; documented assumption).
    flow = min(p.web_transfer_rate_per_gyr * dt_gyr, 0.5)
    sheet_to_filament = sheet * flow
    filament_to_node = filament * flow
    sheet -= sheet_to_filament
    filament += sheet_to_filament - filament_to_node
    node += filament_to_node

    void_vol = min(void_vol + (p.void_volume_fraction_max - void_vol) * p.void_volume_growth_per_gyr * dt_gyr, 1.0)

    metadata = dict(state.metadata)
    metadata.setdefault("regime", StructureRegime.EXPANDING_ASSOCIATION.value)
    # Per-structure regime bookkeeping: dissolving structures that fully
    # decay are flagged (the engine emits the transition event).
    structures: Dict[str, Dict[str, float]] = dict(metadata.get("structures", {}))
    for sid, record in sorted(structures.items()):
        s_sigma = float(record.get("sigma", sigma))
        regime = record.get("regime", web_regime)
        if regime == StructureRegime.GRAVITATIONALLY_BOUND.value:
            s_sigma *= 1.0 + p.web_growth_rate_per_gyr * dt_gyr
        elif regime == StructureRegime.DISSOLVING.value:
            s_sigma *= max(1.0 - p.web_decay_rate_per_gyr * dt_gyr, 0.0)
        record = dict(record)
        record["sigma"] = s_sigma
        if s_sigma < 1.0e-6 and regime == StructureRegime.DISSOLVING.value:
            record["dissolved"] = True
            record["transition_detail"] = (
                f"structure {sid} fully decoupled from the cosmic web (sigma decayed below numerical floor)"
            )
        structures[sid] = record
    metadata["structures"] = structures

    updates = {
        "density_contrast_sigma": _q(sigma, "dimensionless", "regime-dependent reduced-order growth"),
        "node_mass_fraction": _q(node, "dimensionless"),
        "filament_mass_fraction": _q(filament, "dimensionless"),
        "sheet_mass_fraction": _q(sheet, "dimensionless"),
        "void_volume_fraction": _q(void_vol, "dimensionless"),
        "void_size_comoving_mpc": _q(void_comoving, "Mpc", "comoving size is fixed by construction"),
        "void_size_proper_mpc": _q(
            void_proper, "Mpc", "proper size = comoving x supplied scale-factor ratio"
        ),
        "connectivity_index": _q(connectivity, "dimensionless"),
        "age_gyr": _q(age + dt_gyr, "Gyr"),
    }
    return replace(
        state,
        cosmic_time_gyr=state.cosmic_time_gyr + dt_gyr,
        phase=state.phase,
        quantities={**state.quantities, **updates},
        metadata=metadata,
    )


def make_web_state(
    web_id: str,
    cosmic_time_gyr: float,
    *,
    density_contrast_sigma: float = 1.0,
    node_fraction: float = 0.05,
    filament_fraction: float = 0.20,
    sheet_fraction: float = 0.30,
    void_volume_fraction: float = 0.60,
    void_size_comoving_mpc: float = 30.0,
    connectivity_index: float = 1.0,
    scenario=None,
    params: Optional[BuiltinModelParams] = None,
) -> EvolutionState:
    """Factory for a COSMIC_WEB-kind evolution state."""
    p = params or BuiltinModelParams()
    provenance = scenario.provenance if scenario is not None else DataProvenance.SIMULATED_DATA
    projection = scenario.projection_class if scenario is not None else ProjectionClass.NONE
    return EvolutionState(
        object_id=web_id,
        object_kind=KIND_COSMIC_WEB,
        cosmic_time_gyr=cosmic_time_gyr,
        phase=StructureRegime.EXPANDING_ASSOCIATION.value,
        quantities={
            "density_contrast_sigma": _q(density_contrast_sigma, "dimensionless"),
            "node_mass_fraction": _q(node_fraction, "dimensionless"),
            "filament_mass_fraction": _q(filament_fraction, "dimensionless"),
            "sheet_mass_fraction": _q(sheet_fraction, "dimensionless"),
            "void_volume_fraction": _q(void_volume_fraction, "dimensionless"),
            "void_size_comoving_mpc": _q(void_size_comoving_mpc, "Mpc"),
            "void_size_proper_mpc": _q(0.0, "Mpc", "fills on first expansion input"),
            "connectivity_index": _q(connectivity_index, "dimensionless"),
            "age_gyr": _q(0.0, "Gyr"),
        },
        model_id=WEB_MODEL_ID,
        provenance=provenance,
        projection_class=projection,
        metadata={
            "regime": StructureRegime.EXPANDING_ASSOCIATION.value,
            "structures": {},
        },
    )


# ==========================================================================
# Registration
# ==========================================================================
def _stellar_model(p: BuiltinModelParams) -> EvolutionModel:
    return EvolutionModel(
        model_id=STELLAR_MODEL_ID,
        name="Single-star lifecycle (reduced order)",
        description=(
            "Power-law mass-lifetime and mass-luminosity relations drive the "
            "FORMATION -> MAIN_SEQUENCE -> POST_MAIN_SEQUENCE -> REMNANT "
            "lifecycle with configurable remnant thresholds."
        ),
        classification=ModelClassification.DERIVED_MODEL,
        provenance=classification_provenance(ModelClassification.DERIVED_MODEL),
        parameters=_builtin_parameter_quantities(p),
        assumptions=(
            ModelAssumption(
                statement=(
                    "t_MS = 10 Gyr x (M/Msun)^-2.5 and L = (M/Msun)^3.5 are "
                    "order-of-magnitude power-law approximations"
                ),
                valid_regime="~0.5-50 Msun; order-of-magnitude outside",
                outside_behaviour="values quoted as order-of-magnitude estimates only",
            ),
            ModelAssumption(
                statement="post-MS duration taken as a fixed fraction of t_MS",
                valid_regime="single-star populations without binary interaction",
                outside_behaviour="binary evolution is unsupported (LimitationState.UNSUPPORTED_PROCESS)",
            ),
        ),
        limitations=(
            "no mass loss / stellar winds",
            "no binary interaction or mass transfer",
            "remnant masses are reduced-order assignments, not structure models",
            "no remnant cooling curves (constant order-of-magnitude luminosities)",
        ),
        applicable_object_kinds=(KIND_STAR,),
        max_valid_cosmic_time_gyr=1.0e6,
        rate_scale=_stellar_rate_scale,
    )


def _population_model(p: BuiltinModelParams) -> EvolutionModel:
    return EvolutionModel(
        model_id=POPULATION_MODEL_ID,
        name="Stellar population conveyor (reduced order)",
        description=(
            "Cohort table per IMF mass bin with delayed deaths, remnant "
            "production, closed-box metal enrichment, and mass-luminosity "
            "light evolution. Statistical: no individual stars."
        ),
        classification=ModelClassification.SIMULATION,
        provenance=classification_provenance(ModelClassification.SIMULATION),
        parameters=_builtin_parameter_quantities(p),
        assumptions=(
            ModelAssumption(
                statement=(
                    "two-slope power-law IMF (Kroupa-2001-style defaults) with "
                    "exact analytic mass integrals; newborn mass split "
                    "statistically by fixed bin fractions"
                ),
                valid_regime="0.08-100 Msun; simple stellar populations",
                outside_behaviour="mass range edges accumulate into edge bins",
            ),
            ModelAssumption(
                statement=(
                    "smooth turnoff window per bin: stars die linearly over "
                    "cohort_death_window_gyr after their bin's t_MS"
                ),
                valid_regime="window small vs population age spread",
                outside_behaviour="death timing smeared by at most the window width",
            ),
            ModelAssumption(
                statement=(
                    "closed-box chemical evolution; recycled gas re-enters the "
                    "reservoir at the CURRENT metallicity (instantaneous-"
                    "recycling approximation)"
                ),
                valid_regime="no significant gas inflow/outflow",
                outside_behaviour="metallicity errors of order the recycled fraction",
            ),
        ),
        limitations=(
            "post-main-sequence light not resolved per cohort",
            "no stellar multiplicity; core-collapse counts are mass-based "
            "order-of-magnitude proxies, never event counts",
            "no dust, no stellar spectra",
        ),
        applicable_object_kinds=(KIND_POPULATION,),
        max_valid_cosmic_time_gyr=1.0e4,
        rate_scale=_population_rate_scale,
    )


def _galaxy_model(p: BuiltinModelParams) -> EvolutionModel:
    return EvolutionModel(
        model_id=GALAXY_MODEL_ID,
        name="One-zone galaxy evolution (reduced order)",
        description=(
            "Gas-supply star formation, delayed recycling, closed-box "
            "enrichment, fuel-capped SMBH growth with an AGN hysteresis "
            "state machine, and morphology DISTRIBUTION drift."
        ),
        classification=ModelClassification.DERIVED_MODEL,
        provenance=classification_provenance(ModelClassification.DERIVED_MODEL),
        parameters=_builtin_parameter_quantities(p),
        assumptions=(
            ModelAssumption(
                statement="linear star-formation law SFR = gas / t_dep",
                valid_regime="normal star-forming disks; z < ~6 analogue regimes",
                outside_behaviour="starbursts/merger-driven SF not represented",
            ),
            ModelAssumption(
                statement=(
                    "delayed recycling: deaths = stellar_mass / t_return; "
                    "returned fraction configurable"
                ),
                valid_regime="populations older than the recycling timescale",
                outside_behaviour="young populations recycle too slowly in this model",
            ),
            ModelAssumption(
                statement=(
                    "SMBH grows exponentially at an Eddington-ratio x Salpeter "
                    "rate, capped by a gas-fuel coupling; AGN activity follows a "
                    "hysteresis state machine on the gas fraction"
                ),
                valid_regime="population-level growth, not individual accretion physics",
                outside_behaviour="individual AGN light curves unsupported (spec 2.13 honesty rule)",
            ),
            ModelAssumption(
                statement=(
                    "morphology is a probability DISTRIBUTION drifting toward "
                    "gas-fraction tendency anchors (reduced-order tendency model)"
                ),
                valid_regime="secular evolution; no merger-driven morphological transformation",
                outside_behaviour="mergers are caller-recorded events, not modeled transitions",
            ),
        ),
        limitations=(
            "no spatial structure, no dust, no spectra",
            "no autonomous merger prediction (requires an orbital/structure layer; "
            "mergers are recorded explicitly by callers)",
            "galaxy-galaxy environment effects not modeled",
        ),
        applicable_object_kinds=(KIND_GALAXY,),
        max_valid_cosmic_time_gyr=1.0e4,
        rate_scale=_galaxy_rate_scale,
    )


def _cluster_model(p: BuiltinModelParams) -> EvolutionModel:
    return EvolutionModel(
        model_id=CLUSTER_MODEL_ID,
        name="Cluster member aggregate (reduced order)",
        description=(
            "Aggregates member-galaxy evolution totals, optional accretion-"
            "driven mass growth, and a caller-supplied expansion-regime tag. "
            "Member dynamics remain the caller's/N-body's responsibility."
        ),
        classification=ModelClassification.SIMULATION,
        provenance=classification_provenance(ModelClassification.SIMULATION),
        parameters=_builtin_parameter_quantities(p),
        assumptions=(
            ModelAssumption(
                statement=(
                    "cluster mass grows only by the configured accretion "
                    "parameter; clusters are NOT treated as permanently bound"
                ),
                valid_regime="bookkeeping level; no internal dynamics",
                outside_behaviour="regime stays UNKNOWN unless the caller supplies dynamics",
            ),
        ),
        limitations=(
            "no internal N-body dynamics (nbody integration is a caller concern)",
            "no intracluster gas model",
            "merger events are caller-recorded (no Phase 20 orbits exist to predict them)",
        ),
        applicable_object_kinds=(KIND_CLUSTER,),
        max_valid_cosmic_time_gyr=1.0e4,
    )


def _web_model(p: BuiltinModelParams) -> EvolutionModel:
    return EvolutionModel(
        model_id=WEB_MODEL_ID,
        name="Cosmic-web regime evolution (reduced order)",
        description=(
            "Consumes a per-step scale-factor ratio (from an injected "
            "UniverseEvolutionProvider or a caller function) to advance proper "
            "sizes, regime-dependent density-contrast growth, hierarchical "
            "mass inflow (sheets->filaments->nodes), void growth, and "
            "connectivity. Never computes expansion itself."
        ),
        classification=ModelClassification.THEORETICAL,
        provenance=classification_provenance(ModelClassification.THEORETICAL),
        parameters=_builtin_parameter_quantities(p),
        assumptions=(
            ModelAssumption(
                statement=(
                    "density contrast grows exponentially in bound regimes, is "
                    "quenched in expanding associations, decays in dissolving "
                    "regimes (qualitative reduced-order surrogate for linear-"
                    "theory growth)"
                ),
                valid_regime="order-of-magnitude trend statements, not precision growth factors",
                outside_behaviour="trends only; numeric sigma values are not physical growth factors",
            ),
            ModelAssumption(
                statement=(
                    "hierarchical mass inflow sheets->filaments->nodes at a "
                    "configurable rate expresses a qualitative Lambda-CDM-like "
                    "tendency"
                ),
                valid_regime="matter-dominated structure formation trends",
                outside_behaviour="no claim of precision mass redistribution",
            ),
            ModelAssumption(
                statement=(
                    "proper void sizes follow the SUPPLIED scale-factor ratio "
                    "only; no independent expansion and no fixed spherical "
                    "expansion model exists in this package"
                ),
                valid_regime="whenever a scale-factor input is supplied",
                outside_behaviour="refuses to step without an expansion input",
            ),
        ),
        limitations=(
            "requires per-step expansion input (Universe Evolution absent from repo)",
            "no halo catalogs, no particle/grid realizations (Phase 20 absent)",
            "connectivity index is a reduced-order summary, not a topological measure",
        ),
        applicable_object_kinds=(KIND_COSMIC_WEB, KIND_STRUCTURE),
        max_valid_cosmic_time_gyr=1.0e4,
        rate_scale=_web_rate_scale,
    )


def register_builtin_models(
    registry: ModelRegistry,
    params: Optional[BuiltinModelParams] = None,
) -> ModelRegistry:
    """Register the five built-in models with full metadata."""
    p = params or BuiltinModelParams()
    p.validate()
    for model, step in (
        (_stellar_model(p), _stellar_step),
        (_population_model(p), _population_step),
        (_galaxy_model(p), _galaxy_step),
        (_cluster_model(p), _cluster_step),
        (_web_model(p), _web_step),
    ):
        registry.register(model, step)
    return registry


__all__ = [
    "BuiltinModelParams",
    "STELLAR_MODEL_ID",
    "POPULATION_MODEL_ID",
    "GALAXY_MODEL_ID",
    "CLUSTER_MODEL_ID",
    "WEB_MODEL_ID",
    "EXPANSION_INPUT_KEY",
    "main_sequence_lifetime_gyr",
    "main_sequence_luminosity_lsun",
    "remnant_for_mass",
    "remnant_mass_msun",
    "classification_provenance",
    "register_builtin_models",
    "make_star_state",
    "make_population_state",
    "make_galaxy_state",
    "make_cluster_state",
    "make_web_state",
    "classify_structure_regime",
]

