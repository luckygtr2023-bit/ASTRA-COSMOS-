"""ASTRA Theoretical - exceptions.

Contract: every Theoretical-layer error derives from
``astra.core.exceptions.AstraError``. Parameter-validation errors
additionally derive from ``ValueError``.

NOTE (Agent LM): the handoff again referenced ``PermissionClient`` and a
``Serializable`` base class; neither exists in this repository (fourth
occurrence). Immutability is enforced by construction (no mutation
surface on metric objects); persistence uses plain-primitive to_dict /
from_dict. Energy-condition violations are DIAGNOSTICS (they are the
expected physics of speculative metrics), not exceptions; the exceptions
here guard mathematical validity of the models themselves.
"""

from astra.core.exceptions import AstraError


class TheoreticalError(AstraError):
    """Base Theoretical-layer error."""


class InvalidGeometryParameterError(TheoreticalError, ValueError):
    """Raised when a model parameter is non-finite or out of range."""


class FlareOutViolation(TheoreticalError, ValueError):
    """Raised when a wormhole shape function violates the flare-out
    condition b'(r0) < 1 at the throat (Morris-Thorne admissibility)."""


class CausalityOrientationError(TheoreticalError):
    """Raised when a trajectory violates a model's causal-orientation
    policy (e.g. worldlines entering a white hole, which only emits)."""
