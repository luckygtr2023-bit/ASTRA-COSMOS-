"""ASTRA COSMOS — Scientific Mode / Speculation Framework (Phase 22).

CANONICAL classification / provenance / assumptions / warnings / validity
layer for ASTRA. All other packages must import their Provenance type from
here, not declare their own.

Architecture:

    Data / Models
          ↓
    Existing ASTRA Scientific Engines
          ↓
    Phase 22 Classification Layer ← THIS PACKAGE
          ↓
    Provenance / Uncertainty / Assumptions / Warnings
          ↓
    Observation / Simulation / UI

This layer annotates, validates, classifies and explains; it does NOT
recompute physics.
"""

from .assumptions import Assumption, AssumptionRegistry
from .audit import AuditEntry, AuditTrail
from .classification import Classification, ClassificationOrder, Provenance, classify_combination
from .config import Policy, ScientificConfig
from .envelope import EnvelopeRef, ResultEnvelope
from .errors import (
    ScientificBlockingError,
    ScientificError,
    ScientificProvenanceError,
    ScientificValidationError,
    ScientificWarningError,
)
from .models import ModelDescriptor, ModelRegistry, ValidityDomain
from .provenance import DerivationChain, ParameterSource, ProvenanceNode, ProvenanceRef
from .scenario import ScenarioIdentity, ScenarioRegistry
from .uncertainty import UNCERTAINTY_UNKNOWN, Uncertainty, UncertaintyKind, UncertaintyPropagator
from .validity import ValidityChecker, ValidityResult, ValidityViolation
from .warnings import ScientificWarning, WarningCode, WarningSeverity, WarningSink

__all__ = [
    "Classification",
    "Provenance",
    "ClassificationOrder",
    "classify_combination",
    "ProvenanceNode",
    "ProvenanceRef",
    "DerivationChain",
    "ParameterSource",
    "Assumption",
    "AssumptionRegistry",
    "ModelDescriptor",
    "ModelRegistry",
    "ValidityDomain",
    "ValidityChecker",
    "ValidityResult",
    "ValidityViolation",
    "Uncertainty",
    "UncertaintyKind",
    "UncertaintyPropagator",
    "UNCERTAINTY_UNKNOWN",
    "ScientificWarning",
    "WarningCode",
    "WarningSeverity",
    "WarningSink",
    "ScenarioIdentity",
    "ScenarioRegistry",
    "AuditEntry",
    "AuditTrail",
    "ResultEnvelope",
    "EnvelopeRef",
    "ScientificConfig",
    "Policy",
    "ScientificError",
    "ScientificValidationError",
    "ScientificProvenanceError",
    "ScientificWarningError",
    "ScientificBlockingError",
]
