"""Hubble / peculiar / local-gravity velocity decomposition.

The engine MUST NOT double-count cosmological expansion.
    total_velocity = hubble_flow + peculiar_velocity + local_gravity
"""
from __future__ import annotations

from dataclasses import dataclass

from .errors import GalacticNumericalError
from .provenance import Provenance
from .types import Vec3


@dataclass(frozen=True)
class VelocityDecomposition:
    hubble_flow: Vec3
    peculiar_velocity: Vec3
    local_gravity: Vec3

    @property
    def total(self) -> Vec3:
        return self.hubble_flow + self.peculiar_velocity + self.local_gravity

    def provenance(self) -> dict:
        return {
            "hubble_flow": Provenance.DERIVED_DATA,
            "peculiar_velocity": Provenance.SIMULATED_DATA,
            "local_gravity": Provenance.SIMULATED_DATA,
        }

    def to_dict(self) -> dict:
        return {
            "hubble_flow": self.hubble_flow.to_tuple(),
            "peculiar_velocity": self.peculiar_velocity.to_tuple(),
            "local_gravity": self.local_gravity.to_tuple(),
            "total": self.total.to_tuple(),
        }


def hubble_flow_velocity(position_mpc: Vec3, h0_kms_mpc: float) -> Vec3:
    """v_h = H0 * r  (in comoving / low-z approximation).

    position_mpc is comoving position in Mpc, H0 in km/s/Mpc, result in km/s.
    This is a low-z linear approximation; outside its domain caller must
    handle via CosmologyProvider / LimitationState.OUTSIDE_VALID_RANGE.
    """
    if not isinstance(position_mpc, Vec3):
        raise GalacticNumericalError("position_mpc must be Vec3")
    if not isinstance(h0_kms_mpc, (int, float)) or isinstance(h0_kms_mpc, bool):
        raise GalacticNumericalError("H0 must be numeric")
    if h0_kms_mpc <= 0.0 or not __import__("math").isfinite(float(h0_kms_mpc)):
        raise GalacticNumericalError("H0 must be finite > 0")
    return position_mpc * float(h0_kms_mpc)


def decompose_velocity(
    position_mpc: Vec3,
    peculiar_velocity: Vec3,
    local_gravity: Vec3,
    h0_kms_mpc: float = 70.0,
) -> VelocityDecomposition:
    """Build a full decomposition from components, computing Hubble flow.

    Caller supplies peculiar + local_gravity; Hubble flow is DERIVED from
    position and H0.  This single function is the ONLY place Hubble flow
    is computed for galactic dynamics, guaranteeing no double-counting.
    """
    hf = hubble_flow_velocity(position_mpc, h0_kms_mpc)
    return VelocityDecomposition(
        hubble_flow=hf,
        peculiar_velocity=peculiar_velocity,
        local_gravity=local_gravity,
    )
