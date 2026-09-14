"""Row-validation tests: NULL preserved, impossible rejected, nothing guessed."""

import dataclasses
import math

import pytest

from astra.core.exceptions import AstraError
from astra.ingestion import COLUMN_NAMES, GaiaRecord, validate_row
from astra.ingestion.exceptions import (
    IngestionContractError,
    IngestionError,
    IngestionRunError,
    MalformedRowError,
    TransportError,
)
from astra.celestial.provenance import DataProvenance
from test_ingestion_pipeline import make_row

OPTIONAL_COLUMNS = [
    "designation",
    "ref_epoch",
    "ra_error",
    "dec_error",
    "parallax",
    "parallax_error",
    "pmra",
    "pmra_error",
    "pmdec",
    "pmdec_error",
    "radial_velocity",
    "radial_velocity_error",
    "ruwe",
    "astrometric_params_solved",
    "phot_g_mean_mag",
    "phot_bp_mean_mag",
    "phot_rp_mean_mag",
    "bp_rp",
    "teff_gspphot",
    "logg_gspphot",
    "mh_gspphot",
    "distance_gspphot",
    "ag_gspphot",
]

ALL_COLUMNS = ["source_id", "ra", "dec"] + OPTIONAL_COLUMNS

# Numeric columns only: `designation` is free TEXT, so the literal "nan" is a
# legitimate designation string there, not numeric corruption.
NAN_CHECK_COLUMNS = [c for c in ALL_COLUMNS if c != "designation"]


def make_record(sid="1000000000000000001", **overrides):
    """Programmatic GaiaRecord with numeric defaults."""
    defaults = dict(
        source_id=sid,
        designation=None,
        ref_epoch=2016.0,
        ra=12.5,
        ra_error=0.5,
        dec=-30.25,
        dec_error=0.4,
        parallax=1.9,
        parallax_error=0.05,
        pmra=-3.2,
        pmra_error=0.1,
        pmdec=1.1,
        pmdec_error=0.1,
        radial_velocity=None,
        radial_velocity_error=None,
        ruwe=0.95,
        astrometric_params_solved=55,
        phot_g_mean_mag=9.5,
        phot_bp_mean_mag=9.1,
        phot_rp_mean_mag=8.7,
        bp_rp=-0.4,
        teff_gspphot=5800.0,
        logg_gspphot=4.4,
        mh_gspphot=0.0,
        distance_gspphot=520.0,
        ag_gspphot=0.15,
    )
    defaults.update(overrides)
    return GaiaRecord(**defaults)


class TestValidRows:
    def test_valid_row_roundtrip(self):
        record = validate_row(make_row(1_000_000_000_000_000_001))
        assert record.source_id == "1000000000000000001"
        assert record.ra == 12.5
        assert record.dec == -30.25
        assert record.parallax == 1.9
        assert record.pmra == -3.2  # negative proper motion is legitimate
        assert record.radial_velocity is None
        assert record.data_classification is DataProvenance.REAL_DATA

    def test_db_tuple_shape(self):
        record = validate_row(make_row(2))
        blob = record.to_db_tuple()
        assert len(blob) == 27
        assert blob[-1] == "REAL_DATA"
        assert blob[0] == record.source_id

    def test_field_order_matches_schema(self):
        names = [f.name for f in dataclasses.fields(GaiaRecord)]
        assert names[:-1] == list(COLUMN_NAMES)
        assert names[-1] == "data_classification"

    def test_whitespace_is_tolerated(self):
        row = make_row(3, ra=" 12.5 ", dec=" -30.25 ", source_id=" 44 ")
        record = validate_row(row)
        assert record.ra == 12.5
        assert record.source_id == "44"

    def test_negative_radial_velocity_is_legal(self):
        record = validate_row(make_row(4, radial_velocity="-52.5"))
        assert record.radial_velocity == -52.5

    def test_zero_metallicity_is_legal(self):
        record = validate_row(make_row(5, mh_gspphot="0.0"))
        assert record.mh_gspphot == 0.0

    @pytest.mark.parametrize("ra", [0.0, 360.0])
    def test_ra_boundaries_inclusive(self, ra):
        assert validate_row(make_row(6, ra=repr(ra))).ra == ra

    @pytest.mark.parametrize("dec", [-90.0, 90.0])
    def test_dec_boundaries_inclusive(self, dec):
        assert validate_row(make_row(7, dec=repr(dec))).dec == dec

    def test_leading_zero_source_id_is_digits(self):
        assert validate_row(make_row("008")).source_id == "008"


class TestNullPreservation:
    @pytest.mark.parametrize("column", OPTIONAL_COLUMNS)
    @pytest.mark.parametrize("token", ["", "null", "NULL", "\\N", " "])
    def test_null_tokens_stored_as_none(self, column, token):
        record = validate_row(make_row(10, **{column: token}))
        assert getattr(record, column) is None

    def test_missing_ref_epoch_is_never_guessed(self):
        record = validate_row(make_row(11, ref_epoch=""))
        assert record.ref_epoch is None  # NOT 2016.0

    def test_missing_designation_is_not_empty_string(self):
        record = validate_row(make_row(12, designation=""))
        assert record.designation is None


class TestCorruptionRejected:
    @pytest.mark.parametrize("column", NAN_CHECK_COLUMNS)
    @pytest.mark.parametrize("token", ["nan", "NaN", "-nan", "+nan"])
    def test_nan_rejected_in_every_column(self, column, token):
        with pytest.raises(MalformedRowError):
            validate_row(make_row(20, **{column: token}))

    @pytest.mark.parametrize("token", ["inf", "-inf", "Infinity", "1e999"])
    def test_infinity_rejected(self, token):
        with pytest.raises(MalformedRowError):
            validate_row(make_row(21, ra=token))
        with pytest.raises(MalformedRowError):
            validate_row(make_row(22, parallax=token))

    @pytest.mark.parametrize("token", ["abc", "12.5.1", "1,5", "1e"])
    def test_garbage_rejected(self, token):
        with pytest.raises(MalformedRowError):
            validate_row(make_row(23, ra=token))

    def test_short_row_cell_is_rejected(self):
        row = make_row(24)
        row["ra"] = None  # csv restval for a physically short row
        with pytest.raises(MalformedRowError):
            validate_row(row)


class TestRangeAndSignValidation:
    @pytest.mark.parametrize("ra", ["-0.5", "360.5", "400.0", "-360.0"])
    def test_ra_out_of_range(self, ra):
        with pytest.raises(MalformedRowError):
            validate_row(make_row(30, ra=ra))

    @pytest.mark.parametrize("dec", ["-90.0001", "90.5", "-91.0", "1e99"])
    def test_dec_out_of_range(self, dec):
        with pytest.raises(MalformedRowError):
            validate_row(make_row(31, dec=dec))

    @pytest.mark.parametrize("sid", ["", "abc", "12x", "1.0", "-5", "1 2", "None"])
    def test_invalid_source_id(self, sid):
        with pytest.raises(MalformedRowError):
            validate_row(make_row(sid))

    @pytest.mark.parametrize("column", ["parallax", "ruwe", "ref_epoch"])
    @pytest.mark.parametrize("token", ["0", "0.0", "-1.5"])
    def test_nonpositive_strictly_positive_fields(self, column, token):
        with pytest.raises(MalformedRowError):
            validate_row(make_row(32, **{column: token}))

    @pytest.mark.parametrize("column", ["ra_error", "dec_error", "parallax_error",
                                        "pmra_error", "pmdec_error",
                                        "radial_velocity_error"])
    def test_negative_uncertainty_rejected(self, column):
        with pytest.raises(MalformedRowError):
            validate_row(make_row(33, **{column: "-0.1"}))

    @pytest.mark.parametrize("column", ["ra_error", "parallax_error"])
    def test_zero_uncertainty_is_legal(self, column):
        record = validate_row(make_row(34, **{column: "0.0"}))
        assert getattr(record, column) == 0.0

    @pytest.mark.parametrize("token", ["-1", "3.5", "nan"])
    def test_astrometric_params_solved_validated(self, token):
        with pytest.raises(MalformedRowError):
            validate_row(make_row(35, astrometric_params_solved=token))


class TestProgrammaticConstruction:
    def test_bool_rejected_for_floats(self):
        with pytest.raises(MalformedRowError):
            make_record(ra=True)
        with pytest.raises(MalformedRowError):
            make_record(parallax=False)

    def test_bool_rejected_for_int_field(self):
        with pytest.raises(MalformedRowError):
            make_record(astrometric_params_solved=True)

    def test_nan_rejected_programmatically(self):
        with pytest.raises(MalformedRowError):
            make_record(ra=float("nan"))

    def test_inf_rejected_programmatically(self):
        with pytest.raises(MalformedRowError):
            make_record(parallax=float("inf"))

    def test_bad_source_id_programmatic(self):
        with pytest.raises(MalformedRowError):
            make_record(sid="GAIA-0001")
        with pytest.raises(MalformedRowError):
            make_record(sid="")

    def test_bad_classification_programmatic(self):
        with pytest.raises(MalformedRowError):
            make_record(data_classification="REAL_DATA")  # str, not enum

    def test_record_is_frozen(self):
        record = make_record()
        with pytest.raises(dataclasses.FrozenInstanceError):
            record.ra = 99.0

    def test_negative_distance_gspphot_is_model_output_passthrough(self):
        # GSP-Phot columns are model outputs; validation is finiteness only.
        record = make_record(distance_gspphot=-1.0)
        assert record.distance_gspphot == -1.0


class TestExceptionFamily:
    @pytest.mark.parametrize(
        "exc_type",
        [IngestionError, MalformedRowError, IngestionContractError,
         IngestionRunError, TransportError],
    )
    def test_all_derive_from_astra_error(self, exc_type):
        assert issubclass(exc_type, AstraError)

    def test_error_carries_message_and_details(self):
        err = MalformedRowError("bad ra", {"ra": "-1"})
        assert err.message == "bad ra"
        assert err.details == {"ra": "-1"}

    def test_hierarchy(self):
        for exc in (MalformedRowError, IngestionContractError, IngestionRunError,
                    TransportError):
            assert issubclass(exc, IngestionError)
            assert issubclass(exc, AstraError)
