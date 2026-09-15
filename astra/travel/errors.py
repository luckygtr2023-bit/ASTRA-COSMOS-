"""Travel engine exceptions. UNVERIFIED SCAFFOLD reconciled with real ASTRA.

All travel errors derive from astra.core.exceptions.AstraError for
catch-all compatibility, while also preserving distinct types for
validation/causality/numerical failures.
"""
from __future__ import annotations

from astra.core.exceptions import AstraError


class TravelError(AstraError):
    """Base class for travel errors."""


class TravelValidationError(TravelError, ValueError):
    """Invalid request, config, or input."""


class TravelAuthorityError(TravelError):
    """Mutation attempted without authority."""


class TravelCausalityError(TravelError):
    """Causal consistency violation."""


class TravelNumericalError(TravelError, ValueError):
    """NaN, Inf, overflow, singularity, or numerical instability."""


class TravelUnsupportedError(TravelError):
    """Mechanism or regime not supported by the existing architecture."""
