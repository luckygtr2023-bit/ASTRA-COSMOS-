"""ASTRA COSMOS — Phase 21: cosmic-time conventions and interop.

The evolution layer expresses cosmic time in GIGAYEARS (Gyr): epoch
spans of interest reach 1e12+ years, and gigayears keep float64
resolution far below any physically meaningful interval everywhere in
that range.

The rest of ASTRA (astra.temporal) uses SI seconds. This module provides
the ONLY sanctioned conversions. The conversion constants are unit
DEFINITIONS (Julian year = exactly 31557600 s by definition of the unit;
1 Gyr = 1e9 years), not measured physical quantities, so nothing here is
fabricated data.

No new clock type is introduced: cosmic time is a plain float in Gyr
carried by EvolutionState, and ``temporal_state_for`` maps it onto the
existing ``astra.temporal.state.TemporalState`` (five explicit time
quantities, SI seconds) for interop with the temporal layer.
"""
from __future__ import annotations

from astra.relativity.core import SPEED_OF_LIGHT  # noqa: F401  (SI convention anchor)
from astra.temporal.state import TemporalState

from .errors import EvolutionNumericalError
from .quantity import require_finite_number

# Unit definitions (exact by definition of the units, not measurements).
SECONDS_PER_JULIAN_YEAR: float = 31557600.0
SECONDS_PER_GYR: float = 1.0e9 * SECONDS_PER_JULIAN_YEAR
GYR_PER_SECOND: float = 1.0 / SECONDS_PER_GYR


def gyr_to_seconds(cosmic_time_gyr: float) -> float:
    v = require_finite_number(cosmic_time_gyr, "cosmic_time_gyr")
    return v * SECONDS_PER_GYR


def seconds_to_gyr(seconds: float) -> float:
    v = require_finite_number(seconds, "seconds")
    return v * GYR_PER_SECOND


def temporal_state_for(
    state,
    observer: str = "cosmic",
    proper_rate: float = 1.0,
) -> TemporalState:
    """Map an EvolutionState onto the existing temporal-layer state object.

    For a comoving observer in the cosmological background, proper time
    equals cosmic time (rate 1.0). General proper times along worldlines
    remain the business of astra.temporal / astra.spacetime — this helper
    only re-expresses the cosmic time in the temporal layer's units and
    types; it computes no relativity.
    """
    if not hasattr(state, "cosmic_time_gyr"):
        raise EvolutionNumericalError("temporal_state_for requires an EvolutionState-like input")
    r = require_finite_number(proper_rate, "proper_rate")
    if r <= 0.0:
        raise EvolutionNumericalError("proper_rate must be > 0")
    seconds = gyr_to_seconds(state.cosmic_time_gyr)
    return TemporalState(
        simulation_time_s=seconds,
        coordinate_time_s=seconds,
        proper_time_s=seconds * r,
        observer=observer,
        rate=r,
    )


__all__ = [
    "SECONDS_PER_JULIAN_YEAR",
    "SECONDS_PER_GYR",
    "GYR_PER_SECOND",
    "gyr_to_seconds",
    "seconds_to_gyr",
    "temporal_state_for",
]
