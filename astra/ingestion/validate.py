"""Row validation: NULL preserved, impossible rejected, nothing guessed.

VALIDATION POLICY (binding)
    - NULL tokens (``''``, ``'null'``, ``'\\N'`` — case-insensitive) map to
      ``None`` and are stored as SQL NULL. A missing measurement is UNKNOWN,
      never 0.0 and never a substituted default.
    - A token that parses to NaN or ±Infinity in ANY column is data
      corruption: the ROW is rejected (``MalformedRowError``) and counted.
      Corruption is never laundered into NULL.
    - ``source_id`` must be a non-empty decimal-digit string (Gaia's int64
      key). Rows without it are rejected.
    - ``ra`` ∈ [0, 360], ``dec`` ∈ [-90, 90] (ICRS). Coordinates pass
      through UNMODIFIED: this pipeline never re-frames, precesses, or
      "corrects" Gaia astrometry. Reference epoch passes through as
      published; DR3's catalog-wide J2016.0 epoch belongs in catalog
      metadata, never fabricated into rows that lack it.
    - ``parallax`` > 0 when present (this pipeline builds the local-volume
      astrometric sample; non-positive parallaxes cannot survive the
      default query gates either).
    - Uncertainties (``*_error``) ≥ 0 when present; proper motions and
      radial velocity may legitimately be negative; magnitudes pass
      through unsigned (documented pass-through, no silent sign edits).

    ``GaiaRecord`` re-validates in ``__post_init__`` — the same contract
    applies to programmatic construction, not just CSV parsing.
"""

import math
from dataclasses import dataclass
from typing import Mapping, Optional

from astra.celestial.provenance import DataProvenance
from astra.ingestion.exceptions import MalformedRowError
from astra.ingestion.schema import COLUMN_NAMES, ROW_DATA_CLASSIFICATION

#: Tokens that mean "no value" in TAP CSV output (case-insensitive).
NULL_TOKENS = ("", "null", "\\n")


def _is_null_token(token: str) -> bool:
    return token.strip().lower() in NULL_TOKENS


def parse_float(column: str, token: str) -> Optional[float]:
    """Parse one CSV cell to float or None; refuse NaN/Inf/garbage."""
    if not isinstance(token, str):
        raise MalformedRowError(
            f"column {column} is not CSV text",
            {"column": column, "value": repr(token)},
        )
    stripped = token.strip()
    if _is_null_token(stripped):
        return None
    try:
        value = float(stripped)
    except ValueError:
        raise MalformedRowError(
            f"column {column} is not a number",
            {"column": column, "value": repr(token)},
        ) from None
    if not math.isfinite(value):  # catches 'nan', '-nan', 'inf', '1e999', ...
        raise MalformedRowError(
            f"column {column} is not finite",
            {"column": column, "value": repr(token)},
        )
    return value


def parse_int(column: str, token: str) -> Optional[int]:
    """Parse one CSV cell to a non-negative int or None."""
    value = parse_float(column, token)
    if value is None:
        return None
    if value < 0 or value != int(value):
        raise MalformedRowError(
            f"column {column} is not a non-negative integer",
            {"column": column, "value": repr(token)},
        )
    return int(value)


def _require_float(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MalformedRowError(
            f"{label} must be a real number",
            {"field": label, "value": repr(value)},
        )
    value = float(value)
    if not math.isfinite(value):
        raise MalformedRowError(
            f"{label} must be finite", {"field": label, "value": repr(value)}
        )
    return value


def _require_optional(
    value: object,
    label: str,
    *,
    positive: bool = False,
    non_negative: bool = False,
) -> Optional[float]:
    if value is None:
        return None
    value = _require_float(value, label)
    if positive and value <= 0.0:
        raise MalformedRowError(
            f"{label} must be > 0 when present",
            {"field": label, "value": repr(value)},
        )
    if non_negative and value < 0.0:
        raise MalformedRowError(
            f"{label} must be >= 0 when present",
            {"field": label, "value": repr(value)},
        )
    return value


@dataclass(frozen=True)
class GaiaRecord:
    """One validated Gaia DR3 row (frozen; 27 values in canonical order).

    Field order matches :data:`astra.ingestion.schema.COLUMN_NAMES` exactly,
    followed by ``data_classification`` — i.e. the ``stars_astrometry``
    insert order (see ``to_db_tuple``).
    """

    source_id: str
    designation: Optional[str]
    ref_epoch: Optional[float]
    ra: float
    ra_error: Optional[float]
    dec: float
    dec_error: Optional[float]
    parallax: Optional[float]
    parallax_error: Optional[float]
    pmra: Optional[float]
    pmra_error: Optional[float]
    pmdec: Optional[float]
    pmdec_error: Optional[float]
    radial_velocity: Optional[float]
    radial_velocity_error: Optional[float]
    ruwe: Optional[float]
    astrometric_params_solved: Optional[int]
    phot_g_mean_mag: Optional[float]
    phot_bp_mean_mag: Optional[float]
    phot_rp_mean_mag: Optional[float]
    bp_rp: Optional[float]
    teff_gspphot: Optional[float]
    logg_gspphot: Optional[float]
    mh_gspphot: Optional[float]
    distance_gspphot: Optional[float]
    ag_gspphot: Optional[float]
    data_classification: DataProvenance = ROW_DATA_CLASSIFICATION

    def __post_init__(self) -> None:
        # source_id: non-empty decimal-digit string (Gaia int64 key).
        if not isinstance(self.source_id, str) or not self.source_id.isdigit():
            raise MalformedRowError(
                "source_id must be a non-empty decimal-digit string",
                {"source_id": repr(self.source_id)},
            )
        # Coordinates: finite and in ICRS range.
        ra = _require_float(self.ra, "ra")
        if not (0.0 <= ra <= 360.0):
            raise MalformedRowError(
                "ra outside ICRS range [0, 360]",
                {"field": "ra", "value": repr(ra)},
            )
        dec = _require_float(self.dec, "dec")
        if not (-90.0 <= dec <= 90.0):
            raise MalformedRowError(
                "dec outside ICRS range [-90, 90]",
                {"field": "dec", "value": repr(dec)},
            )
        # Optional numerics: parallax/ruwe/ref_epoch strictly positive when
        # present (0.0 is impossible, not missing); errors non-negative;
        # proper motions and radial velocity may be negative.
        _require_optional(self.ref_epoch, "ref_epoch", positive=True)
        _require_optional(self.ra_error, "ra_error", non_negative=True)
        _require_optional(self.dec_error, "dec_error", non_negative=True)
        _require_optional(self.parallax, "parallax", positive=True)
        _require_optional(self.parallax_error, "parallax_error", non_negative=True)
        _require_optional(self.pmra, "pmra")
        _require_optional(self.pmra_error, "pmra_error", non_negative=True)
        _require_optional(self.pmdec, "pmdec")
        _require_optional(self.pmdec_error, "pmdec_error", non_negative=True)
        _require_optional(self.radial_velocity, "radial_velocity")
        _require_optional(
            self.radial_velocity_error, "radial_velocity_error", non_negative=True
        )
        _require_optional(self.ruwe, "ruwe", positive=True)
        if self.astrometric_params_solved is not None:
            aps = self.astrometric_params_solved
            if isinstance(aps, bool) or not isinstance(aps, int) or aps < 0:
                raise MalformedRowError(
                    "astrometric_params_solved must be a non-negative integer",
                    {"value": repr(aps)},
                )
        for label in (
            "phot_g_mean_mag",
            "phot_bp_mean_mag",
            "phot_rp_mean_mag",
            "bp_rp",
            "teff_gspphot",
            "logg_gspphot",
            "mh_gspphot",
            "distance_gspphot",
            "ag_gspphot",
        ):
            _require_optional(getattr(self, label), label)
        if self.designation is not None and not isinstance(self.designation, str):
            raise MalformedRowError(
                "designation must be text or NULL",
                {"value": repr(self.designation)},
            )
        if not isinstance(self.data_classification, DataProvenance):
            raise MalformedRowError(
                "data_classification must be a DataProvenance member",
                {"value": repr(self.data_classification)},
            )

    def to_db_tuple(self) -> tuple:
        """27-value tuple in ``stars_astrometry`` column order."""
        return tuple(getattr(self, name) for name in COLUMN_NAMES) + (
            self.data_classification.value,
        )


def validate_row(row: Mapping[str, Optional[str]]) -> GaiaRecord:
    """Validate one CSV row (mapping of column name -> raw cell text).

    A cell present in the mapping but holding ``None`` means the physical
    row was SHORT (csv restval) — that is a malformed row, distinct from an
    empty cell (a legitimate NULL).
    """
    values = {}
    for name in COLUMN_NAMES:
        if name not in row:
            raise MalformedRowError(
                "row is missing an expected column",
                {"column": name},
            )
        token = row[name]
        if token is None:
            raise MalformedRowError(
                "row is short: cell absent for an expected column",
                {"column": name},
            )
        values[name] = token.strip()

    source_id = values["source_id"]
    if not source_id or not source_id.isdigit():
        raise MalformedRowError(
            "source_id must be a non-empty decimal-digit string",
            {"source_id": repr(source_id)},
        )

    ra = parse_float("ra", values["ra"])
    if ra is None:
        raise MalformedRowError("ra is required", {"column": "ra"})
    dec = parse_float("dec", values["dec"])
    if dec is None:
        raise MalformedRowError("dec is required", {"column": "dec"})

    return GaiaRecord(
        source_id=source_id,
        designation=None if _is_null_token(values["designation"]) else values["designation"],
        ref_epoch=parse_float("ref_epoch", values["ref_epoch"]),
        ra=ra,
        ra_error=parse_float("ra_error", values["ra_error"]),
        dec=dec,
        dec_error=parse_float("dec_error", values["dec_error"]),
        parallax=parse_float("parallax", values["parallax"]),
        parallax_error=parse_float("parallax_error", values["parallax_error"]),
        pmra=parse_float("pmra", values["pmra"]),
        pmra_error=parse_float("pmra_error", values["pmra_error"]),
        pmdec=parse_float("pmdec", values["pmdec"]),
        pmdec_error=parse_float("pmdec_error", values["pmdec_error"]),
        radial_velocity=parse_float("radial_velocity", values["radial_velocity"]),
        radial_velocity_error=parse_float(
            "radial_velocity_error", values["radial_velocity_error"]
        ),
        ruwe=parse_float("ruwe", values["ruwe"]),
        astrometric_params_solved=parse_int(
            "astrometric_params_solved", values["astrometric_params_solved"]
        ),
        phot_g_mean_mag=parse_float("phot_g_mean_mag", values["phot_g_mean_mag"]),
        phot_bp_mean_mag=parse_float("phot_bp_mean_mag", values["phot_bp_mean_mag"]),
        phot_rp_mean_mag=parse_float("phot_rp_mean_mag", values["phot_rp_mean_mag"]),
        bp_rp=parse_float("bp_rp", values["bp_rp"]),
        teff_gspphot=parse_float("teff_gspphot", values["teff_gspphot"]),
        logg_gspphot=parse_float("logg_gspphot", values["logg_gspphot"]),
        mh_gspphot=parse_float("mh_gspphot", values["mh_gspphot"]),
        distance_gspphot=parse_float("distance_gspphot", values["distance_gspphot"]),
        ag_gspphot=parse_float("ag_gspphot", values["ag_gspphot"]),
    )
