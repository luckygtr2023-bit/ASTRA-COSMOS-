"""ASTRA Theoretical - authoritative facade API.

Contract: upstream systems query THIS module only. Dependency direction
(no reverse edges, no cycles):

    CORE -> MATHEMATICS -> PHYSICS -> RELATIVITY -> BLACK-HOLE
         -> SPACETIME -> THEORETICAL

Every model is a mathematical construction with an explicit
ScientificClassification; SPECULATIVE models log a diagnostic warning at
instantiation (astra.core.logging) stating they require unproven
stress-energy parameters. Nothing in this package implements faster-than-
light travel: local light cones of every metric remain causal and ASTRA's
v < c enforcement for massive particles applies unchanged.

Deterministic pure functions over immutable inputs.
"""

from __future__ import annotations

from typing import Callable, Sequence

from astra.core.logging import get_logger
from astra.spacetime.metric import MetricField
from astra.theoretical.classification import (
    CLASSIFICATION_NOTES,
    ScientificClassification,
    default_classification,
    log_speculative_instantiation,
)
from astra.theoretical.energy_conditions import (
    EnergyConditionDiagnostic,
    evaluate_energy_conditions,
)
from astra.theoretical.exceptions import (
    CausalityOrientationError,
    FlareOutViolation,
    InvalidGeometryParameterError,
    TheoreticalError,
)
from astra.theoretical.warp import MAX_WARP_WALL_STEEPNESS, AlcubierreMetric
from astra.theoretical.whitehole import WhiteHoleMetric
from astra.theoretical.wormhole import (
    NUMERICAL_THROAT_EPSILON,
    EinsteinRosenMetric,
    MorrisThorneMetric,
)

_LOGGER = get_logger("theoretical")


def create_morris_thorne_metric(
    throat_radius_m: float,
    shape_func: Callable[[float], float],
    redshift_func: Callable[[float], float] = lambda r: 0.0,
) -> MorrisThorneMetric:
    """Traversable-wormhole mathematical model (SPECULATIVE)."""
    return MorrisThorneMetric(throat_radius_m, shape_func, redshift_func)


def create_einstein_rosen_metric(mass_kg: float) -> EinsteinRosenMetric:
    """Einstein-Rosen bridge (THEORETICAL, non-traversable)."""
    return EinsteinRosenMetric(mass_kg)


def create_white_hole_metric(mass_kg: float) -> WhiteHoleMetric:
    """White-hole exterior model (THEORETICAL, emissive-only policy)."""
    return WhiteHoleMetric(mass_kg)


def create_alcubierre_metric(
    velocity: float, radius_m: float, wall_steepness: float
) -> AlcubierreMetric:
    """Warp-bubble mathematical model (SPECULATIVE; coordinate shift only)."""
    return AlcubierreMetric(velocity, radius_m, wall_steepness)


def get_scientific_classification(metric: MetricField) -> ScientificClassification:
    """Epistemic classification of any metric (ESTABLISHED by default)."""
    return default_classification(metric)


def get_classification_note(metric: MetricField) -> str:
    """Human-readable epistemic annotation for the metric."""
    return CLASSIFICATION_NOTES[get_scientific_classification(metric)]


def evaluate_energy_conditions(
    metric: MetricField, coordinates: Sequence[float]
) -> EnergyConditionDiagnostic:
    """NEC/WEC/SEC/DEC report at a point (violations are diagnostics)."""
    return evaluate_energy_conditions(metric, coordinates)


__all__ = [
    "create_morris_thorne_metric", "create_einstein_rosen_metric",
    "create_white_hole_metric", "create_alcubierre_metric",
    "get_scientific_classification", "get_classification_note",
    "evaluate_energy_conditions", "log_speculative_instantiation",
    # re-exports for convenience
    "ScientificClassification", "EnergyConditionDiagnostic",
    "TheoreticalError", "FlareOutViolation", "CausalityOrientationError",
    "InvalidGeometryParameterError", "MAX_WARP_WALL_STEEPNESS",
    "NUMERICAL_THROAT_EPSILON",
]
