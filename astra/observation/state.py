"""Observed state — immutable, observer-dependent, provenance-tagged.

An ObservedState is DERIVED_DATA (appearance computed from history) and
never mutates the authoritative PhysicalState / HistoricalSnapshot.
It is distinct from astra.temporal.observation.ObservedState but
compatible (conversion helpers). Extended fields cover the spec:

  apparent position/distance/velocity/brightness/angular size
  emission/arrival/lookback timestamps
  redshift decomposition
  reference frame, FOV, observer/source identity, metadata, provenance
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from astra.celestial.provenance import DataProvenance, ProvenanceTag
from astra.spacetime.events import SpacetimeEvent
from astra.observation.redshift import RedshiftComponents

def _finite(v, name: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or math.isnan(float(v)) or math.isinf(float(v)):
        raise ValueError(f"{name} must be finite, got {v!r}")
    return float(v)

@dataclass(frozen=True)
class ObservedState:
    """What an observer actually sees at observation_time_s.

    Immutable; to_dict/from_dict for persistence.

    Fields:
      source_id, observer_id,
      observation_time_s (= arrival), emission_time_s, lookback_time_s,
      apparent_position, apparent_distance_m,
      apparent_velocity (optional, m/s tuple),
      apparent_brightness (W/m2, optional),
      angular_size_rad (optional),
      emission_event, actual_event_at_observation, observer_event,
      redshift: RedshiftComponents,
      reference_frame, provenance, metadata
    """

    source_id: str
    observer_id: str
    observation_time_s: float
    emission_time_s: float
    lookback_time_s: float
    apparent_position: Tuple[float, float, float]
    apparent_distance_m: float
    emission_event: SpacetimeEvent
    actual_event_at_observation: SpacetimeEvent
    observer_event: SpacetimeEvent
    # optional apparent quantities
    apparent_velocity: Optional[Tuple[float, float, float]] = None
    apparent_brightness_w_per_m2: Optional[float] = None
    angular_size_rad: Optional[float] = None
    redshift: RedshiftComponents = field(default_factory=lambda: RedshiftComponents(0,0,0,0, ()))
    reference_frame: str = "inertial"
    provenance: ProvenanceTag = field(default_factory=lambda: ProvenanceTag(DataProvenance.DERIVED_DATA, source_label="astra.observation"))
    metadata: Dict[str, Any] = field(default_factory=dict, compare=False, hash=False)

    def __post_init__(self):
        if not isinstance(self.source_id, str) or not self.source_id:
            raise ValueError("source_id must be non-empty string")
        if not isinstance(self.observer_id, str) or not self.observer_id:
            raise ValueError("observer_id must be non-empty string")
        for name in ("observation_time_s","emission_time_s","lookback_time_s","apparent_distance_m"):
            _finite(getattr(self, name), name)
        if self.lookback_time_s < -1e-12:
            raise ValueError("lookback_time_s must be >=0")
        if self.emission_time_s > self.observation_time_s + 1e-12:
            raise ValueError("emission_time_s cannot be after observation_time_s")
        if abs((self.observation_time_s - self.emission_time_s) - self.lookback_time_s) > 1e-9:
            # allow tiny float error but enforce consistency
            if abs((self.observation_time_s - self.emission_time_s) - self.lookback_time_s) > 1e-6:
                raise ValueError("lookback_time_s != observation - emission")
        # apparent_position
        if not isinstance(self.apparent_position, (list, tuple)) or len(self.apparent_position)!=3:
            raise ValueError("apparent_position must be 3-tuple")
        # distance must match position delta to observer
        for attr in ("emission_event","actual_event_at_observation","observer_event"):
            if not isinstance(getattr(self, attr), SpacetimeEvent):
                raise TypeError(f"{attr} must be SpacetimeEvent")
        if not isinstance(self.provenance, ProvenanceTag):
            raise TypeError("provenance must be ProvenanceTag")
        if self.angular_size_rad is not None:
            v=_finite(self.angular_size_rad, "angular_size_rad")
            if v <0 or v> math.pi:
                raise ValueError("angular_size_rad must be in [0, pi]")
        if self.apparent_brightness_w_per_m2 is not None:
            v=_finite(self.apparent_brightness_w_per_m2, "apparent_brightness_w_per_m2")
            if v <0:
                raise ValueError("apparent_brightness must be >=0")
        if not isinstance(self.redshift, RedshiftComponents):
            raise TypeError("redshift must be RedshiftComponents")
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be dict")

    # -- convenience -----------------------------------------------------
    @property
    def arrival_time_s(self) -> float:
        return self.observation_time_s

    @property
    def is_blueshifted(self) -> bool:
        return self.redshift.total < 0

    @property
    def is_redshifted(self) -> bool:
        return self.redshift.total > 0

    def angular_separation_to(self, other: "ObservedState") -> float:
        """Angular separation between two apparent positions as seen from same observer.

        Returns angle in radians between vectors (apparent_position - observer).
        """
        if self.observer_id != other.observer_id:
            raise ValueError("angular separation requires same observer")
        ox,oy,oz = self.observer_event.x, self.observer_event.y, self.observer_event.z
        v1 = (self.apparent_position[0]-ox, self.apparent_position[1]-oy, self.apparent_position[2]-oz)
        v2 = (other.apparent_position[0]-ox, other.apparent_position[1]-oy, other.apparent_position[2]-oz)
        n1=math.sqrt(v1[0]*v1[0]+v1[1]*v1[1]+v1[2]*v1[2])
        n2=math.sqrt(v2[0]*v2[0]+v2[1]*v2[1]+v2[2]*v2[2])
        if n1==0 or n2==0:
            return 0.0
        dot=(v1[0]*v2[0]+v1[1]*v2[1]+v1[2]*v2[2])/(n1*n2)
        dot=max(-1.0, min(1.0, dot))
        return math.acos(dot)

    # -- persistence -----------------------------------------------------
    def to_dict(self) -> Dict:
        return {
            "source_id": self.source_id,
            "observer_id": self.observer_id,
            "observation_time_s": self.observation_time_s,
            "emission_time_s": self.emission_time_s,
            "lookback_time_s": self.lookback_time_s,
            "apparent_position": list(self.apparent_position),
            "apparent_distance_m": self.apparent_distance_m,
            "apparent_velocity": list(self.apparent_velocity) if self.apparent_velocity else None,
            "apparent_brightness_w_per_m2": self.apparent_brightness_w_per_m2,
            "angular_size_rad": self.angular_size_rad,
            "emission_event": self.emission_event.to_dict(),
            "actual_event_at_observation": self.actual_event_at_observation.to_dict(),
            "observer_event": self.observer_event.to_dict(),
            "redshift": self.redshift.to_dict(),
            "reference_frame": self.reference_frame,
            "provenance": {
                "provenance": self.provenance.provenance.value,
                "source_label": self.provenance.source_label,
            },
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ObservedState":
        from astra.spacetime.events import SpacetimeEvent as SE
        prov = data.get("provenance", {})
        tag = ProvenanceTag(
            provenance=DataProvenance(prov.get("provenance", "DERIVED_DATA")),
            source_label=prov.get("source_label", "astra.observation"),
        )
        rsd = RedshiftComponents.from_dict(data.get("redshift", {"cosmological":0,"doppler":0,"gravitational":0,"total":0}))
        av = data.get("apparent_velocity")
        return cls(
            source_id=data["source_id"],
            observer_id=data["observer_id"],
            observation_time_s=data["observation_time_s"],
            emission_time_s=data["emission_time_s"],
            lookback_time_s=data["lookback_time_s"],
            apparent_position=tuple(data["apparent_position"]),
            apparent_distance_m=data["apparent_distance_m"],
            emission_event=SE.from_dict(data["emission_event"]),
            actual_event_at_observation=SE.from_dict(data["actual_event_at_observation"]),
            observer_event=SE.from_dict(data["observer_event"]),
            apparent_velocity=tuple(av) if av is not None else None,
            apparent_brightness_w_per_m2=data.get("apparent_brightness_w_per_m2"),
            angular_size_rad=data.get("angular_size_rad"),
            redshift=rsd,
            reference_frame=data.get("reference_frame","inertial"),
            provenance=tag,
            metadata=dict(data.get("metadata",{})),
        )

    # -- interop with temporal ObservedState -----------------------------
    @classmethod
    def from_temporal(cls, t_obs_state, source_id: str, observer_id: str,
                      apparent_distance_m: float, **overrides) -> "ObservedState":
        """Wrap a temporal ObservedState into the enriched form."""
        from astra.spacetime.events import SpacetimeEvent as SE
        # t_obs_state has observation_time_s, emission_time_s, lookback_time_s,
        # emission_event, actual_state_at_observation, observer (str)
        # We need observer_event — construct from observer position if not in t_obs_state
        # If not supplied, assume observer at origin at t_obs for interop
        observer_event = overrides.get("observer_event")
        if observer_event is None:
            # fallback: observer at stored position or origin
            obs_pos = overrides.get("observer_position", (0,0,0))
            observer_event = SE.from_coordinates(t_obs_state.observation_time_s, obs_pos[0], obs_pos[1], obs_pos[2])
        return cls(
            source_id=source_id,
            observer_id=observer_id,
            observation_time_s=t_obs_state.observation_time_s,
            emission_time_s=t_obs_state.emission_time_s,
            lookback_time_s=t_obs_state.lookback_time_s,
            apparent_position=(t_obs_state.emission_event.x, t_obs_state.emission_event.y, t_obs_state.emission_event.z),
            apparent_distance_m=apparent_distance_m,
            emission_event=t_obs_state.emission_event,
            actual_event_at_observation=t_obs_state.actual_state_at_observation,
            observer_event=observer_event,
            redshift=overrides.get("redshift", RedshiftComponents(0,0,0,0, ())),
            reference_frame=overrides.get("reference_frame","inertial"),
            provenance=overrides.get("provenance", ProvenanceTag(DataProvenance.DERIVED_DATA, "astra.observation")),
            metadata=overrides.get("metadata", {}),
        )

__all__ = ["ObservedState"]
