"""Deterministic ADQL generation and the 2,000-light-year selection constant.

2,000-LY SELECTION (project policy, documented)
    IAU parsec: 1 pc = 648000/pi AU = 3.26156 ly (approximately).
        2000 ly = 2000 / 3.26156 = 613.2036... pc
        parallax[mas] = 1000 / distance[pc]
        ->  parallax = 1000 x 3.26156 / 2000 = 1.63078 mas (exact in this
        arithmetic; the input constant 3.26156 is itself approximate).

    ``MIN_PARALLAX_MAS_2000LY`` is an APPROXIMATE INVERSE-PARALLAX
    SELECTION, deliberately NOT presented as an exact spherical 2,000-ly
    boundary: under parallax uncertainty a lower bound on measured parallax
    is not an upper bound on distance (stars beyond the nominal radius can
    pass the cut and nearby stars with poor parallaxes can fail it --
    a selection-function caveat that downstream population analyses must
    carry). This module preserves the existing project policy; it does not
    silently reinterpret Gaia coordinates or invent a 3D boundary.

SYNC vs ASYNC (ESA Gaia archive limits, anonymous users)
    Synchronous TAP: 30 s timeout; at most 3,000,000 rows if the query
    finishes within it; a query still running at 30 s is TRUNCATED TO
    2,000 ROWS. Asynchronous (UWS): 90 min timeout, 3,000,000-row cap.
    Therefore: use sync only for probe queries; batch-scale ingestion
    (the local ~2,000-ly sample alone is order 10**7 quality-gated rows)
    must go through the UWS async client (transport.UwsAsyncClient) or a
    partitioned (e.g. HEALPix-chunked) strategy. Full-DR3-scale ingestion
    is explicitly out of scope of the sync path.

DETERMINISM
    ``build_adql`` is a pure function: identical spec -> byte-identical
    ADQL -> identical sha256 (``query_hash``). Floats are formatted with
    ``repr`` (shortest round-trip representation; stable across runs on
    the same platform). No RNG, no timestamps, no dict-order dependence.
"""

import hashlib
import math
from dataclasses import dataclass, field
from typing import Optional

from astra.ingestion.exceptions import IngestionContractError
from astra.ingestion.schema import COLUMN_NAMES

#: IAU parsec expressed in light-years (approximate by definition of "ly").
LY_PER_PARSEC = 3.26156

#: Project selection radius in light-years.
SELECTION_RADIUS_LY = 2000.0

#: Selection radius in parsecs (derived, never duplicated by hand).
SELECTION_RADIUS_PC = SELECTION_RADIUS_LY / LY_PER_PARSEC  # ~613.2036 pc

#: Approximate inverse-parallax cut for the 2,000-ly selection, in mas.
#: parallax[mas] = 1000/pc  =>  1000 * 3.26156 / 2000 = 1.63078 mas.
MIN_PARALLAX_MAS_2000LY = 1000.0 / SELECTION_RADIUS_PC

DEFAULT_PARALLAX_OVER_ERROR = 5.0
DEFAULT_MAX_RUWE = 1.4


def _require_positive(value: object, label: str) -> None:
    """Reject bools, non-numbers, non-finite and non-positive query limits."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise IngestionContractError(
            f"query parameter {label} must be a real number",
            {"parameter": label, "value": repr(value)},
        )
    value = float(value)
    if not math.isfinite(value) or value <= 0.0:
        raise IngestionContractError(
            f"query parameter {label} must be finite and > 0",
            {"parameter": label, "value": repr(value)},
        )


def _fmt(value: float) -> str:
    """Deterministic float rendering for ADQL literals."""
    return repr(float(value))


@dataclass(frozen=True)
class GaiaQuerySpec:
    """Immutable, validated specification of one Gaia DR3 ADQL query.

    ``min_parallax_mas=None`` performs an unbounded (all-sky) gated query --
    legal, but callers wanting the project's local-volume selection should
    pass ``MIN_PARALLAX_MAS_2000LY`` explicitly; the constant is enforced
    by name at call sites and recorded in the ingestion manifest.
    """

    parallax_over_error: float = DEFAULT_PARALLAX_OVER_ERROR
    max_ruwe: float = DEFAULT_MAX_RUWE
    min_parallax_mas: Optional[float] = None
    columns: tuple[str, ...] = field(default=COLUMN_NAMES)

    def __post_init__(self) -> None:
        _require_positive(self.parallax_over_error, "parallax_over_error")
        _require_positive(self.max_ruwe, "max_ruwe")
        if self.min_parallax_mas is not None:
            _require_positive(self.min_parallax_mas, "min_parallax_mas")
        if not self.columns:
            raise IngestionContractError(
                "query spec requires at least one column",
                {"columns": repr(self.columns)},
            )
        unknown = [c for c in self.columns if c not in COLUMN_NAMES]
        if unknown:
            raise IngestionContractError(
                "query spec references unknown Gaia columns",
                {"unknown": unknown},
            )
        # Preserve canonical order so the ADQL (and its hash) is canonical.
        ordered = tuple(c for c in COLUMN_NAMES if c in self.columns)
        if ordered != tuple(self.columns):
            object.__setattr__(self, "columns", ordered)


def build_adql(spec: GaiaQuerySpec) -> str:
    """Build the canonical ADQL string for ``spec`` (pure, deterministic)."""
    where = [
        "parallax IS NOT NULL",
        f"parallax_over_error > {_fmt(spec.parallax_over_error)}",
        f"ruwe < {_fmt(spec.max_ruwe)}",
    ]
    if spec.min_parallax_mas is not None:
        where.append(f"parallax >= {_fmt(spec.min_parallax_mas)}")
    return (
        "SELECT "
        + ", ".join(spec.columns)
        + "\nFROM gaiadr3.gaia_source\nWHERE "
        + "\n  AND ".join(where)
    )


def query_hash(adql: str) -> str:
    """sha256 hex digest of the ADQL text (manifest / reproducibility key)."""
    return hashlib.sha256(adql.encode("utf-8")).hexdigest()
