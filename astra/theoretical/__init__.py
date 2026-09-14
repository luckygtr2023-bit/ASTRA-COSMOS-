"""ASTRA Theoretical layer.

Dependency direction:
    CORE -> MATHEMATICS -> PHYSICS -> RELATIVITY -> BLACK-HOLE
         -> SPACETIME -> THEORETICAL

Mathematical constructions in historical/general-relativistic literature,
each carrying an explicit ScientificClassification:

    MorrisThorneMetric   (SPECULATIVE) traversable wormhole; exotic matter
                         required (NEC violated at the throat - diagnostic).
    EinsteinRosenMetric  (THEORETICAL) non-traversable bridge; delegates to
                         the spacetime layer's Schwarzschild implementation.
    WhiteHoleMetric      (THEORETICAL) emissive-only causal-orientation
                         policy over the (identical) exterior geometry.
    AlcubierreMetric     (SPECULATIVE) warp-bubble metric; the shift vector
                         is a COORDINATE parameter - local light cones stay
                         causal and ASTRA's v < c law is untouched.

Energy-condition diagnostics (NEC/WEC/SEC/DEC) quantify the stress-energy
these geometries require; violations are reported as data, never silently.

Scope: prescribed fixed backgrounds (test-particle approximation); no
backreaction; no closed-timelike-curve machinery (explicitly out of scope);
1D (x-axis) warp orientation this phase.

Determinism: 100% deterministic - no RNG, no wall-clock, no global state.
"""
from astra.theoretical.classification import (
    CLASSIFICATION_NOTES,
    ScientificClassification,
    default_classification,
    log_speculative_instantiation,
)
from astra.theoretical.exceptions import (
    TheoreticalError,
    InvalidGeometryParameterError,
    FlareOutViolation,
    CausalityOrientationError,
)
from astra.theoretical.wormhole import (
    NUMERICAL_THROAT_EPSILON,
    EinsteinRosenMetric,
    MorrisThorneMetric,
)
from astra.theoretical.whitehole import EMISSIVE_BAND_RELATIVE, WhiteHoleMetric
from astra.theoretical.warp import MAX_WARP_WALL_STEEPNESS, AlcubierreMetric
from astra.theoretical.energy_conditions import (
    EnergyConditionDiagnostic,
    evaluate_energy_conditions,
)
from astra.theoretical import api
from astra.theoretical.api import (
    create_morris_thorne_metric,
    create_einstein_rosen_metric,
    create_white_hole_metric,
    create_alcubierre_metric,
    get_scientific_classification,
    get_classification_note,
)

__all__ = [
    # classification
    "ScientificClassification", "CLASSIFICATION_NOTES",
    "default_classification", "log_speculative_instantiation",
    # exceptions
    "TheoreticalError", "InvalidGeometryParameterError",
    "FlareOutViolation", "CausalityOrientationError",
    # models
    "MorrisThorneMetric", "EinsteinRosenMetric", "WhiteHoleMetric",
    "AlcubierreMetric",
    # diagnostics
    "EnergyConditionDiagnostic", "evaluate_energy_conditions",
    # policy constants
    "NUMERICAL_THROAT_EPSILON", "EMISSIVE_BAND_RELATIVE",
    "MAX_WARP_WALL_STEEPNESS",
    # facade
    "api", "create_morris_thorne_metric", "create_einstein_rosen_metric",
    "create_white_hole_metric", "create_alcubierre_metric",
    "get_scientific_classification", "get_classification_note",
]
