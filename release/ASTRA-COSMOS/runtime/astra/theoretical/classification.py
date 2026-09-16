"""ASTRA Theoretical - scientific classification of geometric models.

Contract: every theoretical geometry carries an explicit, machine-readable
classification separating established physics from mathematically-valid-but
unobserved solutions and from models requiring exotic matter. The
classification is read-only metadata: it can never be spoofed after
construction (frozen enum property per class).
"""

from __future__ import annotations

from enum import Enum


class ScientificClassification(Enum):
    """Epistemic status of a geometric model.

    ESTABLISHED : observationally grounded (Minkowski, Schwarzschild...).
    THEORETICAL : mathematically valid Einstein Field Equation solutions
                  without observational confirmation (Einstein-Rosen bridge,
                  white holes).
    SPECULATIVE : requires unproven energy conditions / exotic matter
                  (Morris-Thorne traversable wormholes, Alcubierre warp).
    """

    ESTABLISHED = "ESTABLISHED"
    THEORETICAL = "THEORETICAL"
    SPECULATIVE = "SPECULATIVE"


# Machine-readable annotations used by the facade and the diagnostics layer.
CLASSIFICATION_NOTES = {
    ScientificClassification.ESTABLISHED:
        "Observationally established geometry.",
    ScientificClassification.THEORETICAL:
        "Mathematical solution of the Einstein Field Equations without "
        "observational proof; not known to exist in nature.",
    ScientificClassification.SPECULATIVE:
        "This model evaluates speculative mathematical physics requiring "
        "unproven stress-energy parameters (violates classical energy "
        "conditions; exotic matter required).",
}


def default_classification(metric) -> ScientificClassification:
    """Classification of any MetricField: ESTABLISHED unless overridden.

    Lookup is CLASS-LEVEL ONLY: instances cannot shadow or spoof the
    epistemic tag after construction. Established astra.spacetime metrics
    (Minkowski, Schwarzschild, Kerr) do not carry the attribute; they are
    established physics by default.
    """
    return getattr(type(metric), "classification", ScientificClassification.ESTABLISHED)


def log_speculative_instantiation(metric) -> None:
    """Deterministic diagnostic warning for SPECULATIVE models.

    Defined here (not in api.py) to keep the module dependency graph
    acyclic: metric modules may announce their own classification without
    importing the facade.
    """
    from astra.core.logging import get_logger

    if getattr(metric, "classification", None) is ScientificClassification.SPECULATIVE:
        get_logger("theoretical").warning(
            "SPECULATIVE MODEL INSTANTIATED: " + type(metric).__name__ + ". "
            + CLASSIFICATION_NOTES[ScientificClassification.SPECULATIVE]
        )
