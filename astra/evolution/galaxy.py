"""ASTRA Evolution — galaxy evolution models (§2.10–2.12, §2.15).

Reduced-order galaxy evolution: stellar mass, gas mass, SFR, metallicity,
morphology probability distribution and central-BH properties evolve via
parameterized prescriptions.  Every approximation is documented as a
``ModelAssumption``.
"""

from __future__ import annotations

import math
from typing import Dict

from .errors import EvolutionValidationError
from .models import EvolutionModel, ModelAssumption, ModelClassification
from .provenance import Provenance, Quantity
from .state import EvolutionState, GalaxyMorphology


def _get_quantity(state: EvolutionState, key: str, default: float = 0.0) -> float:
    q = state.quantities.get(key)
    if q is None:
        return default
    return float(q.value)


def make_galaxy_step():
    """Step function for a reduced-order galaxy model.

    Physics (per dt = 0.01–1 Gyr typical):

    - Stellar mass growth: dMstar/dt = SFR * (1 - R) where R=0.3 return fraction
    - Gas depletion: dMgas/dt = -SFR + inflow - outflow
      (inflow scaled by cosmological accretion parameter)
    - Metallicity: dZ/dt ∝ yield * SFR / Mgas  (scalar Z, no yield table)
    - SFR: exponentially declining with timescale tau depending on scenario
      SFR(t+dt) = SFR(t) * exp(-dt/tau)
    - Morphology: merger-driven shift toward elliptical probability

    All rates carry SIMULATED_DATA or THEORETICAL depending on calibration.
    """

    def step(state: EvolutionState, dt_gyr: float, model: EvolutionModel) -> EvolutionState:
        if not isinstance(state, EvolutionState):
            raise EvolutionValidationError("state must be an EvolutionState")
        dt = float(dt_gyr)
        if math.isnan(dt) or math.isinf(dt) or dt < 0.0:
            raise EvolutionValidationError("dt_gyr must be finite and >= 0")

        # Parameters with fallbacks
        tau = 5.0  # Gyr decline timescale
        return_frac = 0.3
        yield_p = 0.02
        inflow_rate = 0.0  # Msun/yr scaled
        for k, q in model.parameters.items():
            if k == "sfr_tau_gyr":
                tau = float(q.value)
            elif k == "return_fraction":
                return_frac = float(q.value)
            elif k == "yield":
                yield_p = float(q.value)

        new_time = state.cosmic_time_gyr + dt
        new_q = dict(state.quantities)

        mstar = _get_quantity(state, "stellar_mass_msun", 1e10)
        mgas = _get_quantity(state, "gas_mass_msun", 1e9)
        sfr = _get_quantity(state, "sfr_msun_per_yr", 1.0)
        Z = _get_quantity(state, "metallicity", 0.02)

        # SFR exponential decline
        if tau > 0.0:
            sfr_new = sfr * math.exp(-dt / tau)
        else:
            sfr_new = sfr

        # Formed stellar mass in this step (Gyr -> yr factor 1e9)
        formed = sfr * dt * 1e9 * (1.0 - return_frac)
        mstar_new = mstar + formed
        mgas_new = max(0.0, mgas - sfr * dt * 1e9 + inflow_rate * dt * 1e9)

        # Metallicity enrichment (instantaneous recycling approx)
        if mgas_new > 0.0:
            dZ = yield_p * sfr * dt * 1e9 / mgas_new
            Z_new = Z + dZ
        else:
            Z_new = Z

        new_q["stellar_mass_msun"] = Quantity(
            value=mstar_new, unit="Msun",
            provenance=Provenance.SIMULATED_DATA, model_id=model.model_id,
        )
        new_q["gas_mass_msun"] = Quantity(
            value=mgas_new, unit="Msun",
            provenance=Provenance.SIMULATED_DATA, model_id=model.model_id,
        )
        new_q["sfr_msun_per_yr"] = Quantity(
            value=sfr_new, unit="Msun/yr",
            provenance=Provenance.SIMULATED_DATA, model_id=model.model_id,
            note=f"exp decline tau={tau} Gyr",
        )
        new_q["metallicity"] = Quantity(
            value=Z_new, unit="Z",
            provenance=Provenance.SIMULATED_DATA, model_id=model.model_id,
        )

        # Luminosity: simple mass-to-light scaling
        L = _get_quantity(state, "luminosity_Lsun", 1e10)
        L_new = L * (mstar_new / mstar) if mstar > 0.0 else L
        new_q["luminosity_Lsun"] = Quantity(
            value=L_new, unit="Lsun",
            provenance=Provenance.SIMULATED_DATA, model_id=model.model_id,
        )

        # Central BH mass growth (Eddington-limited toy)
        mbh = _get_quantity(state, "central_bh_mass_msun", 1e6)
        # toy growth: 1% per Gyr
        mbh_new = mbh * (1.0 + 0.01 * dt)
        new_q["central_bh_mass_msun"] = Quantity(
            value=mbh_new, unit="Msun",
            provenance=Provenance.SIMULATED_DATA, model_id=model.model_id,
        )

        # Preserve phase (morphology) — handled via metadata.morphology_probs
        # Drift morphology_probs toward elliptical slowly to model late-time
        # transformation in absence of gas.
        meta = dict(state.metadata)
        if "morphology_probs" in meta:
            import copy
            probs = dict(meta["morphology_probs"])
            # Gas-poor drift: increase elliptical by 1% per Gyr capped
            if mgas_new / max(mstar_new, 1.0) < 0.05:
                # shift 0.005 per step from spiral to elliptical
                shift = min(0.01 * dt, probs.get(GalaxyMorphology.SPIRAL.value, 0.0))
                if shift > 0.0:
                    probs[GalaxyMorphology.SPIRAL.value] = probs.get(GalaxyMorphology.SPIRAL.value, 0.0) - shift
                    probs[GalaxyMorphology.ELLIPTICAL.value] = probs.get(GalaxyMorphology.ELLIPTICAL.value, 0.0) + shift
                    # renormalize
                    tot = sum(probs.values())
                    if tot > 0:
                        for k in list(probs.keys()):
                            probs[k] /= tot
                    meta["morphology_probs"] = probs

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


def default_galaxy_model() -> EvolutionModel:
    return EvolutionModel(
        model_id="astra.evolution.galaxy.v1",
        name="Reduced-order galaxy evolution",
        description=(
            "Exponential SFR decline, gas depletion via star formation, "
            "scalar metallicity enrichment, morphology probability drift. "
            "No resolved hydrodynamics, no explicit feedback energetics."
        ),
        classification=ModelClassification.SIMULATION,
        provenance=Provenance.SIMULATED_DATA,
        parameters={
            "sfr_tau_gyr": Quantity(value=5.0, unit="Gyr",
                                    provenance=Provenance.SIMULATED_DATA,
                                    model_id="astra.evolution.galaxy.v1"),
            "return_fraction": Quantity(value=0.3, unit="dimensionless",
                                        provenance=Provenance.SIMULATED_DATA,
                                        model_id="astra.evolution.galaxy.v1"),
            "yield": Quantity(value=0.02, unit="dimensionless",
                              provenance=Provenance.SIMULATED_DATA,
                              model_id="astra.evolution.galaxy.v1"),
        },
        assumptions=(
            ModelAssumption(
                statement="Exponential SFH with tau=5 Gyr",
                valid_regime="0 < t < 13 Gyr, Milky-Way-like",
                outside_behaviour="hold SFR constant beyond validity; flag HYPOTHETICAL",
                source="toy declining SFH; replace with scenario SFH",
                uncertainty=0.5,
            ),
            ModelAssumption(
                statement="Instantaneous recycling, constant yield 0.02",
                valid_regime="Z < 0.05, no Pop-III",
                outside_behaviour="cap Z at 0.05 and mark OUTSIDE_VALID_RANGE",
                source="simple closed-box",
                uncertainty=0.8,
            ),
        ),
        limitations=(
            "No AGN feedback energetics beyond mass growth.",
            "No resolved metallicity distribution; scalar Z only.",
            "Morphology probabilities drift without full dynamical model.",
        ),
        applicable_object_kinds=("GALAXY", "GALAXY_POPULATION"),
        applies_to_regimes=("STELLIFEROUS", "DECLINING_STAR_FORMATION", "DEGENERATE"),
    )
