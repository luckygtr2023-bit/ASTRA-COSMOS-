"""Impact momentum computation.

    p_rel        = m_reduced * v_rel
    p_transferred = p_rel * momentum_transfer_efficiency   (model parameter)
    p_residual    = p_rel - p_transferred                  (exact identity)
"""
from __future__ import annotations

from .config import DestructionConfig
from .types import ImpactEvent, ImpactMomentum
from .provenance import DataProvenance


def compute_impact_momentum(
    event: ImpactEvent,
    config: DestructionConfig,
) -> ImpactMomentum:
    m_red = event.reduced_mass()
    v_rel = event.relative_velocity()
    p_rel = v_rel * m_red
    transferred = p_rel * config.momentum_transfer_efficiency
    residual = p_rel - transferred
    return ImpactMomentum(
        relative_momentum_kg_m_s=p_rel,
        transferred_momentum_kg_m_s=transferred,
        residual_momentum_kg_m_s=residual,
        provenance=DataProvenance.SIMULATED_DATA,
    )
