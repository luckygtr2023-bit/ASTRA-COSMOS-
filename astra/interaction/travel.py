"""ASTRA Interaction — travel integration via authoritative Travel Engine.

This module NEVER implements travel physics. It validates and delegates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Any, Protocol, Tuple
import math

from .errors import TravelError
from astra.scientific.classification import Classification


class TravelMethod(str, Enum):
    CONVENTIONAL_RELATIVISTIC = "CONVENTIONAL_RELATIVISTIC"
    STRONG_GRAVITY_TRAJECTORY = "STRONG_GRAVITY_TRAJECTORY"
    WORMHOLE = "WORMHOLE"
    WARP = "WARP"
    TEMPORAL_DISPLACEMENT = "TEMPORAL_DISPLACEMENT"
    SPECULATIVE = "SPECULATIVE"


@dataclass(frozen=True)
class TravelConstraints:
    requires_energy_j: Optional[float] = None
    requires_stability: Optional[float] = None  # 0..1
    max_proper_time_s: Optional[float] = None
    causal: bool = True
    allowed_classifications: Tuple[Classification, ...] = (
        Classification.REAL_DATA,
        Classification.DERIVED_DATA,
        Classification.SIMULATED_DATA,
        Classification.THEORETICAL,
        Classification.HYPOTHETICAL,
        Classification.SPECULATIVE,
    )

    def __post_init__(self):
        if self.requires_energy_j is not None:
            if isinstance(self.requires_energy_j, bool) or not isinstance(self.requires_energy_j, (int, float)) or math.isnan(self.requires_energy_j) or math.isinf(self.requires_energy_j) or self.requires_energy_j < 0:
                raise TravelError("requires_energy_j must be finite >=0 or None")
        if self.requires_stability is not None:
            if not 0.0 <= float(self.requires_stability) <= 1.0:
                raise TravelError("requires_stability must be in [0,1]")
        for c in self.allowed_classifications:
            if not isinstance(c, Classification):
                raise TravelError("allowed_classifications must be Classification")
        object.__setattr__(self, "allowed_classifications", tuple(self.allowed_classifications))


@dataclass(frozen=True)
class TravelRequest:
    request_id: str
    method: TravelMethod
    target_id: str
    origin_frame_id: Optional[str] = None
    destination_frame_id: Optional[str] = None
    classification: Classification = Classification.SIMULATED_DATA
    constraints: TravelConstraints = field(default_factory=TravelConstraints)
    parameters: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.request_id, str) or not self.request_id:
            raise TravelError("request_id must be non-empty string")
        if not isinstance(self.method, TravelMethod):
            raise TravelError("method must be TravelMethod")
        if not isinstance(self.target_id, str) or not self.target_id:
            raise TravelError("target_id must be non-empty string")
        if not isinstance(self.classification, Classification):
            raise TravelError("classification must be Classification")
        if not isinstance(self.constraints, TravelConstraints):
            raise TravelError("constraints must be TravelConstraints")
        if self.classification not in self.constraints.allowed_classifications:
            raise TravelError(f"classification {self.classification} not allowed by constraints")
        object.__setattr__(self, "parameters", dict(self.parameters))

    def to_dict(self) -> Dict:
        return {
            "request_id": self.request_id,
            "method": self.method.value,
            "target_id": self.target_id,
            "origin_frame_id": self.origin_frame_id,
            "destination_frame_id": self.destination_frame_id,
            "classification": self.classification.value,
            "constraints": {
                "requires_energy_j": self.constraints.requires_energy_j,
                "requires_stability": self.constraints.requires_stability,
                "max_proper_time_s": self.constraints.max_proper_time_s,
                "causal": self.constraints.causal,
                "allowed_classifications": [c.value for c in self.constraints.allowed_classifications],
            },
            "parameters": dict(self.parameters),
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "TravelRequest":
        c = d.get("constraints", {})
        return cls(
            request_id=d["request_id"],
            method=TravelMethod(d["method"]),
            target_id=d["target_id"],
            origin_frame_id=d.get("origin_frame_id"),
            destination_frame_id=d.get("destination_frame_id"),
            classification=Classification(d.get("classification", "SIMULATED_DATA")),
            constraints=TravelConstraints(
                requires_energy_j=c.get("requires_energy_j"),
                requires_stability=c.get("requires_stability"),
                max_proper_time_s=c.get("max_proper_time_s"),
                causal=c.get("causal", True),
                allowed_classifications=tuple(Classification(x) for x in c.get("allowed_classifications", [x.value for x in Classification])),
            ),
            parameters=dict(d.get("parameters", {})),
        )


@dataclass(frozen=True)
class TravelResult:
    request_id: str
    success: bool
    method: TravelMethod
    classification: Classification
    proper_time_s: Optional[float] = None
    coordinate_time_s: Optional[float] = None
    energy_j: Optional[float] = None
    stability: Optional[float] = None
    causal_status: str = "UNKNOWN"
    warnings: Tuple[Dict, ...] = ()
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "request_id": self.request_id,
            "success": self.success,
            "method": self.method.value,
            "classification": self.classification.value,
            "proper_time_s": self.proper_time_s,
            "coordinate_time_s": self.coordinate_time_s,
            "energy_j": self.energy_j,
            "stability": self.stability,
            "causal_status": self.causal_status,
            "warnings": list(self.warnings),
            "error_code": self.error_code,
            "error_message": self.error_message,
        }


class TravelProvider(Protocol):
    """Authoritative travel engine provider (injected)."""

    def can_travel(self, req: TravelRequest) -> Tuple[bool, str]:
        ...

    def initiate(self, req: TravelRequest) -> TravelResult:
        ...

    def status(self, request_id: str) -> TravelResult:
        ...


class NullTravelProvider:
    """Failing adapter — raises TravelError on any use (ABSENT dependency)."""

    def can_travel(self, req: TravelRequest) -> Tuple[bool, str]:
        raise TravelError("travel provider unavailable: no authoritative Travel Engine injected")
    def initiate(self, req: TravelRequest) -> TravelResult:
        raise TravelError("travel provider unavailable")
    def status(self, request_id: str) -> TravelResult:
        raise TravelError("travel provider unavailable")


class DelegatingTravelService:
    """Validates requests against classification/constraints, delegates to provider."""

    # Map speculative methods to required classification strength
    _METHOD_MIN_CLASS = {
        TravelMethod.CONVENTIONAL_RELATIVISTIC: Classification.SIMULATED_DATA,
        TravelMethod.STRONG_GRAVITY_TRAJECTORY: Classification.SIMULATED_DATA,
        TravelMethod.WORMHOLE: Classification.SPECULATIVE,  # Morris-Thorne is SPECULATIVE
        TravelMethod.WARP: Classification.SPECULATIVE,
        TravelMethod.TEMPORAL_DISPLACEMENT: Classification.HYPOTHETICAL,
        TravelMethod.SPECULATIVE: Classification.SPECULATIVE,
    }

    def __init__(self, provider: Optional[TravelProvider] = None):
        self._provider = provider or NullTravelProvider()

    def validate(self, req: TravelRequest) -> None:
        # No silent strengthening
        from astra.scientific.classification import ClassificationOrder
        required = self._METHOD_MIN_CLASS[req.method]
        # Speculative methods require speculative classification (or weaker)
        # Real methods must not be marked speculative to fake feasibility
        if req.method in (TravelMethod.WORMHOLE, TravelMethod.WARP, TravelMethod.SPECULATIVE):
            if ClassificationOrder.strength(req.classification) < ClassificationOrder.strength(Classification.HYPOTHETICAL):
                raise TravelError(f"{req.method.value} requires HYPOTHETICAL or SPECULATIVE classification, got {req.classification.value}")
        # Energy requirement check placeholder (delegated, but we validate finiteness)
        if req.constraints.requires_energy_j is not None and req.constraints.requires_energy_j > 1e40:
            # extreme energy - not impossible but warn via error if provider would reject
            pass

    def can_travel(self, req: TravelRequest) -> Tuple[bool, str]:
        self.validate(req)
        try:
            return self._provider.can_travel(req)
        except TravelError as e:
            return (False, str(e))

    def initiate(self, req: TravelRequest) -> TravelResult:
        self.validate(req)
        # Delegate; never compute physics here
        result: TravelResult = self._provider.initiate(req)
        # Ensure result classification is not silently strengthened
        from astra.scientific.classification import ClassificationOrder, classify_combination
        # The result must be at least as weak as request
        if ClassificationOrder.strength(result.classification) < ClassificationOrder.strength(req.classification):
            raise TravelError(f"travel result silently strengthened classification: {req.classification} -> {result.classification}")
        return result
