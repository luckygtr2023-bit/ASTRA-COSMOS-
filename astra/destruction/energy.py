"""Impact energy computation and partitioning.

Physics basis (two-body, centre-of-momentum frame):
    E_kin   = 1/2 * m_reduced * |v_rel|^2
    E_dep   = E_kin * deposited_fraction        (modelled; config-level)
    E_frag  = E_dep * fragmentation_energy_fraction
    E_therm = E_dep * thermal_energy_fraction
    E_resid = E_kin - E_frag - E_therm          (exact bookkeeping identity)

The deposited fraction and the partition fractions are MODEL PARAMETERS
(SIMULATED_DATA), not first-principles derivations; this is deliberate and
documented. The surviving residual kinetic energy keeps the total budget
exact: E_frag + E_therm + E_resid == E_kin (up to float round-off).
"""
from __future__ import annotations

from .config import DestructionConfig
from .errors import NumericalError
from .types import ImpactEnergy, ImpactEvent
from .provenance import DataProvenance


def compute_impact_energy(
    event: ImpactEvent,
    config: DestructionConfig,
    *,
    deposited_fraction: float = 0.5,
) -> ImpactEnergy:
    if not (0.0 <= deposited_fraction <= 1.0):
        raise NumericalError("deposited_fraction must be in [0,1]")

    m_red = event.reduced_mass()
    v_rel = event.relative_speed()
    e_kin = 0.5 * m_red * v_rel * v_rel

    e_dep = e_kin * deposited_fraction
    e_frag = e_dep * config.fragmentation_energy_fraction
    e_therm = e_dep * config.thermal_energy_fraction
    e_resid = e_kin - e_frag - e_therm

    if e_resid < -1e-9 * max(e_kin, 1.0):
        raise NumericalError("energy partitioning produced negative residual energy")

    return ImpactEnergy(
        kinetic_energy_j=e_kin,
        deposited_energy_j=e_dep,
        fragmentation_energy_j=e_frag,
        thermal_energy_j=e_therm,
        residual_kinetic_energy_j=e_resid,
        provenance=DataProvenance.SIMULATED_DATA,
    )
