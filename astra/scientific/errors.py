"""ASTRA Scientific — error hierarchy (integrity layer).

No generic Exception is raised by the scientific layer; each failure
mode has a specific subclass.
"""

from __future__ import annotations


class ScientificError(Exception):
    """Base class for scientific-integrity errors."""


class ScientificValidationError(ScientificError):
    """Invalid input, config, model descriptor, or uncertainty."""


class ScientificProvenanceError(ScientificError):
    """Missing, malformed, or inconsistent provenance chain."""


class ScientificWarningError(ScientificError):
    """A warning reached ERROR severity under the active policy."""


class ScientificBlockingError(ScientificError):
    """A BLOCKING warning was raised under STRICT or STANDARD policy."""
