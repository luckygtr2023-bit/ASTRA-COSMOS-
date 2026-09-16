"""ASTRA Evolution — large-scale structure models (§2.16–2.21).

Covers cluster, supercluster, cosmic-web, void and dark-matter halo
evolution via reduced-order prescriptions.  Dark matter is represented
only through the existing LSS halo abstractions — no fabricated particle
physics (§2.21).  Every approximation carries a ModelAssumption.
"""

from __future__ import annotations

import math
from typing import Dict

from .errors import EvolutionValidationError
from .models import EvolutionModel, ModelAssumption, ModelClassification
from .provenance import Provenance, Quantity
from .state import EvolutionState, StructureRegime


def _get(state: EvolutionState, key: str, default: float = 0.0) -> float:
    q = state.quantities.get(key)
    return float(q.value) if q is not None else default


def make_cluster_step():
    """Cluster evolution: mass growth via mergers, member count evolution."""

    def step(state: EvolutionState, dt_gyr: float, model: EvolutionModel) -> EvolutionState:
        dt = float(dt_gyr)
        if math.isnan(dt) or math.isinf(dt) or dt < 0.0:
            raise EvolutionValidationError("dt_gyr must be finite and >= 0")
        new_time = state.cosmic_time_gyr + dt
        mass = _get(state, "total_mass_msun", 1e14)
        members = int(_get(state, "member_count", 50))

        # Toy mass growth: 2% per Gyr through accretion + mergers
        growth_rate = 0.02
        for k, q in model.parameters.items():
            if k == "cluster_growth_rate_per_gyr":
                growth_rate = float(q.value)
        mass_new = mass * (1.0 + growth_rate * dt)
        # Member count grows slowly at late times
        members_new = members + int(0.5 * dt)

        new_q = dict(state.quantities)
        new_q["total_mass_msun"] = Quantity(
            value=mass_new, unit="Msun",
            provenance=Provenance.SIMULATED_DATA, model_id=model.model_id,
        )
        new_q["member_count"] = Quantity(
            value=float(members_new), unit="count",
            provenance=Provenance.SIMULATED_DATA, model_id=model.model_id,
        )
        return EvolutionState(
            object_id=state.object_id,
            cosmic_time_gyr=new_time,
            phase=state.phase,
            quantities=new_q,
            model_id=model.model_id,
            provenance=Provenance.SIMULATED_DATA,
            metadata=dict(state.metadata),
        )

    return step


def make_cosmic_web_step():
    """Cosmic-web connectivity evolution (§2.19)."""

    def step(state: EvolutionState, dt_gyr: float, model: EvolutionModel) -> EvolutionState:
        dt = float(dt_gyr)
        if math.isnan(dt) or math.isinf(dt) or dt < 0.0:
            raise EvolutionValidationError("dt_gyr must be finite and >= 0")
        new_time = state.cosmic_time_gyr + dt
        filaments = int(_get(state, "filament_count", 10))
        nodes = int(_get(state, "node_count", 5))
        voids = int(_get(state, "void_count", 8))

        # Toy: filament growth early, then stabilization
        # Drift toward fewer, thicker filaments as web coarsens
        filaments_new = max(1, filaments - int(0.1 * dt)) if new_time > 10 else filaments
        voids_new = voids + int(0.05 * dt)

        new_q = dict(state.quantities)
        new_q["filament_count"] = Quantity(
            value=float(filaments_new), unit="count",
            provenance=Provenance.SIMULATED_DATA, model_id=model.model_id,
            note="coarsening via reduced-order filament merger",
        )
        new_q["void_count"] = Quantity(
            value=float(voids_new), unit="count",
            provenance=Provenance.SIMULATED_DATA, model_id=model.model_id,
        )
        new_q["node_count"] = Quantity(
            value=float(nodes), unit="count",
            provenance=Provenance.SIMULATED_DATA, model_id=model.model_id,
        )
        meta = dict(state.metadata)
        # Regime remains as before; expansion vs bound determined by model
        return EvolutionState(
            object_id=state.object_id,
            cosmic_time_gyr=new_time,
            phase=state.phase,
            quantities=new_q,
            model_id=model.model_id,
            provenance=Provenance.SIMULATED_DATA,
            metadata=meta,
        )

    return step


def make_void_step():
    """Void evolution (§2.18): characteristic size and density contrast."""

    def step(state: EvolutionState, dt_gyr: float, model: EvolutionModel) -> EvolutionState:
        dt = float(dt_gyr)
        if math.isnan(dt) or math.isinf(dt) or dt < 0.0:
            raise EvolutionValidationError("dt_gyr must be finite and >= 0")
        new_time = state.cosmic_time_gyr + dt
        radius = _get(state, "radius_mpc", 10.0)
        delta = _get(state, "density_contrast", -0.8)  # negative

        # Spherical expansion toy: R ∝ a(t) for expanding association,
        # unless model says DISSOLVING.  Without real cosmology, use
        # linear growth 1% per Gyr.
        growth = 0.01
        for k, q in model.parameters.items():
            if k == "void_growth_per_gyr":
                growth = float(q.value)
        radius_new = radius * (1.0 + growth * dt)
        # Density contrast becomes more negative as void empties
        delta_new = max(-1.0, delta - 0.01 * dt)

        new_q = dict(state.quantities)
        new_q["radius_mpc"] = Quantity(
            value=radius_new, unit="Mpc",
            provenance=Provenance.THEORETICAL,
            model_id=model.model_id,
            note="spherical expansion approximation; see StructureRegime",
        )
        new_q["density_contrast"] = Quantity(
            value=delta_new, unit="dimensionless",
            provenance=Provenance.THEORETICAL,
            model_id=model.model_id,
        )
        return EvolutionState(
            object_id=state.object_id,
            cosmic_time_gyr=new_time,
            phase=state.phase,
            quantities=new_q,
            model_id=model.model_id,
            provenance=Provenance.THEORETICAL,
            metadata=dict(state.metadata),
        )

    return step


def make_dark_matter_halo_step():
    """Halo / dark-matter distribution (§2.21): halo growth via mergers."""

    def step(state: EvolutionState, dt_gyr: float, model: EvolutionModel) -> EvolutionState:
        dt = float(dt_gyr)
        if math.isnan(dt) or math.isinf(dt) or dt < 0.0:
            raise EvolutionValidationError("dt_gyr must be finite and >= 0")
        new_time = state.cosmic_time_gyr + dt
        m_halo = _get(state, "halo_mass_msun", 1e12)
        concentration = _get(state, "concentration", 5.0)

        rate = 0.02
        for k, q in model.parameters.items():
            if k == "halo_growth_per_gyr":
                rate = float(q.value)
        m_new = m_halo * (1.0 + rate * dt)
        c_new = concentration * (1.0 + 0.005 * dt)  # slow increase

        new_q = dict(state.quantities)
        new_q["halo_mass_msun"] = Quantity(
            value=m_new, unit="Msun",
            provenance=Provenance.SIMULATED_DATA, model_id=model.model_id,
        )
        new_q["concentration"] = Quantity(
            value=c_new, unit="dimensionless",
            provenance=Provenance.SIMULATED_DATA, model_id=model.model_id,
        )
        return EvolutionState(
            object_id=state.object_id,
            cosmic_time_gyr=new_time,
            phase=state.phase,
            quantities=new_q,
            model_id=model.model_id,
            provenance=Provenance.SIMULATED_DATA,
            metadata=dict(state.metadata),
        )

    return step


# ---------------------------------------------------------------------------
# Model metadata helpers
# ---------------------------------------------------------------------------

def default_cluster_model() -> EvolutionModel:
    return EvolutionModel(
        model_id="astra.evolution.cluster.v1",
        name="Reduced-order cluster evolution",
        description="Halo mass growth 2% per Gyr; member count via slow accretion. No resolved hydro/gas evolution.",
        classification=ModelClassification.SIMULATION,
        provenance=Provenance.SIMULATED_DATA,
        parameters={
            "cluster_growth_rate_per_gyr": Quantity(value=0.02, unit="1/Gyr",
                                                    provenance=Provenance.SIMULATED_DATA,
                                                    model_id="astra.evolution.cluster.v1"),
        },
        assumptions=(
            ModelAssumption(
                statement="Cluster mass grows ~2% per Gyr via mergers",
                valid_regime="z < 2, M > 1e13 Msun",
                outside_behaviour="hold constant beyond validity; mark HYPOTHETICAL",
                uncertainty=0.6,
            ),
        ),
        limitations=("No ICM gas evolution; no detailed merger tree.",),
        applicable_object_kinds=("CLUSTER", "GROUP"),
        applies_to_regimes=("STELLIFEROUS", "DECLINING_STAR_FORMATION", "DEGENERATE"),
    )


def default_cosmic_web_model() -> EvolutionModel:
    return EvolutionModel(
        model_id="astra.evolution.web.v1",
        name="Coarse-grained cosmic-web evolution",
        description="Filament coarsening and void growth via reduced-order counts; no density-field solve.",
        classification=ModelClassification.SIMULATION,
        provenance=Provenance.THEORETICAL,
        assumptions=(
            ModelAssumption(
                statement="Filaments merge / thicken on Gyr timescales",
                valid_regime="linear to mildly non-linear regime",
                outside_behaviour="freeze counts; tag THEORETICAL",
                uncertainty=0.7,
            ),
        ),
        limitations=("No particle-level dark-matter physics; use N-body for precision.",),
        applicable_object_kinds=("COSMIC_WEB", "SUPERCLUSTER", "FILAMENT"),
        applies_to_regimes=("STELLIFEROUS", "DECLINING_STAR_FORMATION", "DEGENERATE", "BLACK_HOLE_DOMINATED"),
    )


def default_void_model() -> EvolutionModel:
    return EvolutionModel(
        model_id="astra.evolution.void.v1",
        name="Spherical void expansion (approx)",
        description=(
            "Spherical void R(t) ~ 1% per Gyr expansion; density contrast drifts to -1. "
            "Tagged THEORETICAL + ModelAssumption when used; not a replacement for "
            "anisotropic void dynamics."
        ),
        classification=ModelClassification.THEORETICAL,
        provenance=Provenance.THEORETICAL,
        parameters={
            "void_growth_per_gyr": Quantity(value=0.01, unit="1/Gyr",
                                            provenance=Provenance.THEORETICAL,
                                            model_id="astra.evolution.void.v1"),
        },
        assumptions=(
            ModelAssumption(
                statement="Fixed spherical expansion at 1% per Gyr",
                valid_regime="isolated void, no major mergers",
                outside_behaviour="mark HYPOTHETICAL and exposeLimitationState.UNSUPPORTED_STRUCTURE if filament connectivity changes",
                uncertainty=0.9,
            ),
        ),
        limitations=("Spherical symmetry is a coarse approximation; real voids are anisotropic.",),
        applicable_object_kinds=("VOID",),
        applies_to_regimes=("STELLIFEROUS", "DECLINING_STAR_FORMATION", "DEGENERATE"),
    )


def default_halo_model() -> EvolutionModel:
    return EvolutionModel(
        model_id="astra.evolution.halo.v1",
        name="Halo growth (abundance-matched)",
        description="Halo mass growth ~2% per Gyr; concentration slow increase. No particle DM.",
        classification=ModelClassification.SIMULATION,
        provenance=Provenance.SIMULATED_DATA,
        parameters={
            "halo_growth_per_gyr": Quantity(value=0.02, unit="1/Gyr",
                                            provenance=Provenance.SIMULATED_DATA,
                                            model_id="astra.evolution.halo.v1"),
        },
        assumptions=(
            ModelAssumption(
                statement="Smooth halo growth 2% per Gyr",
                valid_regime="M_halo > 1e10 Msun, z < 3",
                outside_behaviour="outside regime return UNSUPPORTED_STRUCTURE",
                uncertainty=0.5,
            ),
        ),
        limitations=("No subhalo structure; no particle-level DM.",),
        applicable_object_kinds=("HALO", "DARK_MATTER_HALO"),
        applies_to_regimes=("STELLIFEROUS", "DECLINING_STAR_FORMATION"),
    )
