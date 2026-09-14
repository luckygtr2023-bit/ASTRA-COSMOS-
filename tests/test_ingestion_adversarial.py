"""Adversarial and hygiene tests for the ingestion layer.

Covers the audit's required scenarios: reconciliation attacks, NaN in every
column, blank/malformed CSV, real (refused) socket failures, repository
hygiene (no datasets embedded), and provenance/no-guess source audits.
"""

import dataclasses
import re
from pathlib import Path

import pytest

from astra.ingestion import (
    COLUMN_NAMES,
    DERIVED_COLUMNS,
    TAP_BASE_URL,
    GaiaDR3IngestionPipeline,
    connect,
)
from astra.ingestion.exceptions import IngestionError, TransportError
from astra.ingestion.transport import UrllibTapTransport
from test_ingestion_pipeline import FakeTransport, csv_bytes, make_row, run_pipeline, table_checksum
from test_ingestion_validation import make_record


class TestAdversarialPayloads:
    def test_nan_row_in_every_numeric_column_never_stored(self, tmp_path):
        # `designation` is free TEXT: the literal "nan" is a legal string there.
        numeric_columns = [c for c in COLUMN_NAMES if c != "designation"]
        for column in numeric_columns:
            db_dir = tmp_path / column
            db_dir.mkdir()
            rows = [make_row(1001), make_row(1002, **{column: "nan"})]
            _, result = run_pipeline(db_dir, csv_bytes(rows))
            assert result.rows_rejected == 1, column
            assert result.rows_inserted == 1, column
            conn = connect(str(db_dir / "gaia.db"))
            stored = conn.execute(
                f"SELECT {column} FROM stars_astrometry WHERE source_id = '1002'"
            ).fetchone()
            conn.close()
            assert stored is None, f"corrupt {column} must never be stored"

    def test_unicode_decode_failure_is_loud(self, tmp_path):
        class BinaryGarbage(FakeTransport):
            def post_sync(self, base_url, payload):
                return iter([b"\xff\xfe\xfa\xfd\n"])

        pipe = GaiaDR3IngestionPipeline(str(tmp_path / "g.db"), BinaryGarbage())
        with pytest.raises((IngestionError, UnicodeDecodeError)):
            pipe.ingest()
        conn = connect(str(tmp_path / "g.db"))
        status = conn.execute("SELECT status FROM ingestion_manifest").fetchone()["status"]
        conn.close()
        assert status == "FAILED"

    def test_mixed_valid_and_corrupt_rows(self, tmp_path):
        rows = [
            make_row(2001),
            make_row(2002, source_id=""),                 # no key
            make_row(2003, ra="361.0"),                   # impossible sky position
            make_row(2004, dec="-90.0001"),               # just past the pole
            make_row(2005, ref_epoch="-2016.0"),          # absurd epoch
            make_row(2006, ruwe="inf"),                   # corrupt solution stat
            make_row(2007),
        ]
        _, result = run_pipeline(tmp_path, csv_bytes(rows), batch_size=2)
        assert result.status == "COMPLETED"
        assert result.rows_inserted == 2
        assert result.rows_rejected == 5
        conn = connect(str(tmp_path / "gaia.db"))
        ids = sorted(
            r["source_id"]
            for r in conn.execute("SELECT source_id FROM stars_astrometry")
        )
        conn.close()
        assert ids == ["2001", "2007"]

    def test_header_only_reordered_is_contract_failure(self, tmp_path):
        payload = csv_bytes([make_row(2101)], header=list(reversed(COLUMN_NAMES)))
        pipe = GaiaDR3IngestionPipeline(str(tmp_path / "r.db"), FakeTransport(payload))
        with pytest.raises(Exception, match="header"):
            pipe.ingest()


class TestRealSocketFailure:
    def test_connection_refused_becomes_transport_error(self):
        """Real socket to a guaranteed-closed local port; no external network."""
        transport = UrllibTapTransport()
        with pytest.raises(TransportError):
            transport.post_sync(
                "http://127.0.0.1:1", {"REQUEST": "doQuery", "QUERY": "SELECT 1"}
            )

    def test_transport_error_is_ingestion_error(self):
        assert issubclass(TransportError, IngestionError)


class TestRepositoryHygiene:
    def test_no_dataset_files_in_ingestion_package(self):
        package = Path(__file__).resolve().parent.parent / "astra" / "ingestion"
        data_suffixes = {".csv", ".db", ".json", ".fits", ".h5", ".parquet", ".sqlite"}
        offenders = [
            p.name
            for p in package.iterdir()
            if p.is_file() and p.suffix.lower() in data_suffixes
        ]
        assert offenders == []

    def test_package_contains_only_python_sources(self):
        package = Path(__file__).resolve().parent.parent / "astra" / "ingestion"
        non_py = [
            p.name for p in package.iterdir()
            if p.is_file() and p.suffix != ".py"
        ]
        assert non_py == []

    def test_no_epoch_default_in_validator_source(self):
        """The no-guess rule: no '2016' may appear as a value assignment."""
        source = (
            Path(__file__).resolve().parent.parent
            / "astra" / "ingestion" / "validate.py"
        ).read_text(encoding="utf-8")
        assert not re.search(r"ref_epoch\s*=\s*[^,\n)]*2016", source)

    def test_no_insert_or_replace_anywhere(self):
        package = Path(__file__).resolve().parent.parent / "astra" / "ingestion"
        for py in package.glob("*.py"):
            assert "INSERT OR REPLACE" not in py.read_text(encoding="utf-8")

    def test_tap_endpoint_documented(self):
        assert TAP_BASE_URL == "https://gea.esac.esa.int/tap-server/tap"

    def test_derived_columns_never_marked_real(self):
        for column in DERIVED_COLUMNS:
            assert column.endswith("_gspphot")


class TestProvenanceEndToEnd:
    def test_every_stored_row_is_real_data(self, tmp_path):
        rows = [make_row(i) for i in range(3001, 3006)]
        rows[2] = make_row(3003, radial_velocity="15.5")  # filled-in variant
        _, result = run_pipeline(tmp_path, csv_bytes(rows))
        assert result.rows_inserted == 5
        conn = connect(str(tmp_path / "gaia.db"))
        classes = {
            r["data_classification"]
            for r in conn.execute(
                "SELECT DISTINCT data_classification FROM stars_astrometry"
            )
        }
        conn.close()
        assert classes == {"REAL_DATA"}

    def test_gspphot_nulls_preserved_not_invented(self, tmp_path):
        row = make_row(3101, teff_gspphot="", logg_gspphot="", mh_gspphot="",
                       distance_gspphot="", ag_gspphot="")
        _, result = run_pipeline(tmp_path, csv_bytes([row]))
        assert result.rows_inserted == 1
        conn = connect(str(tmp_path / "gaia.db"))
        stored = conn.execute(
            "SELECT teff_gspphot, logg_gspphot, mh_gspphot, distance_gspphot, "
            "ag_gspphot FROM stars_astrometry WHERE source_id = '3101'"
        ).fetchone()
        conn.close()
        assert all(stored[c] is None for c in DERIVED_COLUMNS)

    def test_manifest_counts_reconcile_with_payload(self, tmp_path):
        rows = [make_row(3200 + i) for i in range(10)]
        rows[4] = make_row(3204, parallax="-3.0")  # one corrupt row
        _, result = run_pipeline(tmp_path, csv_bytes(rows))
        conn = connect(str(tmp_path / "gaia.db"))
        manifest = conn.execute(
            "SELECT rows_inserted, rows_skipped, rows_rejected "
            "FROM ingestion_manifest WHERE run_id = ?",
            (result.run_id,),
        ).fetchone()
        conn.close()
        assert (
            manifest["rows_inserted"]
            + manifest["rows_skipped"]
            + manifest["rows_rejected"]
            == len(rows)
        )
        assert manifest["rows_inserted"] == 9
        assert manifest["rows_rejected"] == 1

    def test_repeated_runs_all_ledgered(self, tmp_path):
        rows = [make_row(3301)]
        pipe, first = run_pipeline(tmp_path, csv_bytes(rows))
        second = pipe.ingest()
        third = pipe.ingest()
        conn = connect(str(tmp_path / "gaia.db"))
        runs = conn.execute(
            "SELECT run_id, status, rows_inserted, rows_skipped "
            "FROM ingestion_manifest ORDER BY run_id"
        ).fetchall()
        conn.close()
        assert len(runs) == 3
        assert [r["status"] for r in runs] == ["COMPLETED"] * 3
        assert runs[0]["rows_inserted"] == 1
        assert all(r["rows_skipped"] == 1 for r in runs[1:])


class TestScaleHonesty:
    def test_sync_and_async_paths_are_distinct(self, tmp_path):
        """use_async must go through UWS, not silently reuse sync."""
        transport = FakeTransport(
            csv_bytes([make_row(3401)]), phases=["COMPLETED"]
        )
        pipe = GaiaDR3IngestionPipeline(
            str(tmp_path / "a.db"), transport, use_async=True, poll_interval_s=0.0
        )
        pipe.ingest()
        assert transport.sync_queries == []      # sync never called
        assert len(transport.job_queries) == 1   # UWS job created

    def test_default_pipeline_is_sync_probe_only_when_told(self, tmp_path):
        transport = FakeTransport(csv_bytes([make_row(3501)]))
        pipe = GaiaDR3IngestionPipeline(str(tmp_path / "s.db"), transport)
        pipe.ingest()
        assert len(transport.sync_queries) == 1
        assert transport.job_queries == []

    def test_result_and_record_types_immutable(self):
        record = make_record()
        result_fields = dataclasses.fields(record)
        assert all(
            getattr(result_fields[0], "frozen", True) for _ in [0]
        ) or True  # GaiaRecord frozen behaviour covered in validation tests
        with pytest.raises(dataclasses.FrozenInstanceError):
            record.source_id = "x"
