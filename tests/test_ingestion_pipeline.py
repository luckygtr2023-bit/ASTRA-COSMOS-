"""End-to-end pipeline tests with a fake TAP transport (NO network).

All row data in this file is SYNTHETIC test plumbing — SIMULATED_DATA-class
fixtures exercising parser/validation/storage logic. Nothing here represents
real Gaia catalog content and nothing is written into the repository tree
(databases live in pytest tmp_path only).
"""

import csv
import dataclasses
import hashlib
import io
import threading
import time

import pytest

from astra.core.exceptions import AstraError
from astra.ingestion import (
    COLUMN_NAMES,
    GaiaDR3IngestionPipeline,
    GaiaQuerySpec,
    MIN_PARALLAX_MAS_2000LY,
    connect,
    build_adql,
    query_hash,
)
from astra.ingestion.exceptions import (
    IngestionContractError,
    TransportError,
)


# ---------------------------------------------------------------------------
# Synthetic payload helpers
# ---------------------------------------------------------------------------

_TOKEN_DEFAULTS = {
    "source_id": None,  # always overridden
    "designation": "Gaia DR3 {sid}",
    "ref_epoch": "2016.0",
    "ra": "12.5",
    "ra_error": "0.5",
    "dec": "-30.25",
    "dec_error": "0.4",
    "parallax": "1.9",
    "parallax_error": "0.05",
    "pmra": "-3.2",
    "pmra_error": "0.1",
    "pmdec": "1.1",
    "pmdec_error": "0.1",
    "radial_velocity": "",
    "radial_velocity_error": "",
    "ruwe": "0.95",
    "astrometric_params_solved": "55",
    "phot_g_mean_mag": "9.5",
    "phot_bp_mean_mag": "9.1",
    "phot_rp_mean_mag": "8.7",
    "bp_rp": "-0.4",
    "teff_gspphot": "5800",
    "logg_gspphot": "4.4",
    "mh_gspphot": "0.0",
    "distance_gspphot": "520",
    "ag_gspphot": "0.15",
}


def make_row(sid, **overrides):
    """One synthetic row as a {column: token} dict."""
    row = {c: t for c, t in _TOKEN_DEFAULTS.items()}
    row["source_id"] = str(sid)
    row["designation"] = row["designation"].format(sid=sid)
    for name, token in overrides.items():
        row[name] = token
    return row


def csv_bytes(rows, header=None):
    """Serialize synthetic rows to TAP-style CSV text (proper quoting)."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(list(header if header is not None else COLUMN_NAMES))
    for row in rows:
        if isinstance(row, dict):
            writer.writerow([row[c] for c in COLUMN_NAMES])
        else:  # pre-serialized raw cell list (for short/long row tests)
            writer.writerow(row)
    return buf.getvalue()


def table_checksum(db_path):
    """sha256 over the sorted content of stars_astrometry (idempotency proof)."""
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM stars_astrometry ORDER BY source_id"
        ).fetchall()
        payload = repr([tuple(r) for r in rows]).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Fake transport (the only seam the tests ever exercise)
# ---------------------------------------------------------------------------

class FakeTransport:
    """Scripted TAP transport: payloads in, no sockets touched."""

    def __init__(
        self,
        payload=None,
        *,
        fail_on_sync=False,
        fail_after_lines=None,
        phases=None,
    ):
        self.payload = None if payload is None else payload.encode("utf-8")
        self.sync_queries = []
        self.job_queries = []
        self._fail_on_sync = fail_on_sync
        self._fail_after_lines = fail_after_lines
        self._phases = list(phases) if phases is not None else ["COMPLETED"]

    def _lines(self):
        if self._fail_after_lines is None:
            return iter(self.payload.splitlines(keepends=True))

        def generator():
            for index, line in enumerate(self.payload.splitlines(keepends=True)):
                if index >= self._fail_after_lines:
                    raise TransportError(
                        "simulated mid-stream network failure",
                        {"after_lines": index},
                    )
                yield line

        return generator()

    def post_sync(self, base_url, payload):
        if self._fail_on_sync:
            raise TransportError("simulated connection refusal", {"stage": "sync"})
        self.sync_queries.append(payload["QUERY"])
        return self._lines()

    def uws_create_job(self, base_url, adql):
        self.job_queries.append(adql)
        return base_url.rstrip("/") + "/async/job-1"

    def uws_set_phase(self, job_url, phase):
        self.job_phase_sets = getattr(self, "job_phase_sets", [])
        self.job_phase_sets.append(phase)

    def uws_get_phase(self, job_url):
        if len(self._phases) > 1:
            return self._phases.pop(0)
        return self._phases[0]

    def stream_url(self, url):
        return self._lines()


def run_pipeline(tmp_path, payload, *, spec=None, transport=None, **kwargs):
    db = str(tmp_path / "gaia.db")
    pipe = GaiaDR3IngestionPipeline(
        db,
        transport if transport is not None else FakeTransport(payload),
        spec,
        **kwargs,
    )
    return pipe, pipe.ingest()


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------

class TestEndToEnd:
    def test_three_valid_rows(self, tmp_path):
        rows = [make_row(i) for i in range(1001, 1004)]
        _, result = run_pipeline(tmp_path, csv_bytes(rows), batch_size=2)
        assert result.status == "COMPLETED"
        assert result.rows_inserted == 3
        assert result.rows_skipped == 0
        assert result.rows_rejected == 0
        assert result.batches_committed == 2  # batch_size=2 -> 2 + 1

    def test_null_optionals_stored_as_null(self, tmp_path):
        row = make_row(
            2001,
            ref_epoch="",
            designation="",
            radial_velocity="",
            teff_gspphot="",
        )
        _, result = run_pipeline(tmp_path, csv_bytes([row]))
        assert result.rows_inserted == 1
        conn = connect(str(tmp_path / "gaia.db"))
        stored = conn.execute(
            "SELECT ref_epoch, designation, radial_velocity, teff_gspphot "
            "FROM stars_astrometry WHERE source_id = '2001'"
        ).fetchone()
        conn.close()
        assert stored["ref_epoch"] is None  # never guessed to 2016.0
        assert stored["designation"] is None  # never coerced to ''
        assert stored["radial_velocity"] is None
        assert stored["teff_gspphot"] is None

    def test_rows_match_payload_values(self, tmp_path):
        row = make_row(3001, ra="101.33", dec="-45.5", parallax="2.75")
        _, result = run_pipeline(tmp_path, csv_bytes([row]))
        assert result.rows_inserted == 1
        conn = connect(str(tmp_path / "gaia.db"))
        stored = conn.execute(
            "SELECT ra, dec, parallax, data_classification "
            "FROM stars_astrometry WHERE source_id = '3001'"
        ).fetchone()
        conn.close()
        assert stored["ra"] == 101.33
        assert stored["dec"] == -45.5
        assert stored["parallax"] == 2.75
        assert stored["data_classification"] == "REAL_DATA"

    def test_quoted_designation_with_comma(self, tmp_path):
        row = make_row(4001)
        row["designation"] = 'Gaia DR3 4001, field 7'
        _, result = run_pipeline(tmp_path, csv_bytes([row]))
        assert result.rows_inserted == 1
        conn = connect(str(tmp_path / "gaia.db"))
        stored = conn.execute(
            "SELECT designation FROM stars_astrometry WHERE source_id = '4001'"
        ).fetchone()
        conn.close()
        assert stored["designation"] == "Gaia DR3 4001, field 7"

    def test_blank_lines_skipped_not_rejected(self, tmp_path):
        payload = (
            csv_bytes([make_row(5001)])
            + "\n"
            + ",".join(make_row(5002)[c] for c in COLUMN_NAMES)
            + "\n\n"
        )
        _, result = run_pipeline(tmp_path, payload)
        assert result.status == "COMPLETED"
        assert result.rows_inserted == 2
        assert result.rows_rejected == 0

    def test_crlf_line_endings(self, tmp_path):
        payload = csv_bytes([make_row(6001), make_row(6002)]).replace("\n", "\r\n")
        _, result = run_pipeline(tmp_path, payload)
        assert result.rows_inserted == 2

    def test_duplicate_source_id_within_batch(self, tmp_path):
        first = make_row(7001, ra="10.0")
        second = make_row(7001, ra="20.0")  # same key, different body
        _, result = run_pipeline(tmp_path, csv_bytes([first, second]))
        assert result.rows_inserted == 1
        assert result.rows_skipped == 1
        conn = connect(str(tmp_path / "gaia.db"))
        stored = conn.execute(
            "SELECT ra FROM stars_astrometry WHERE source_id = '7001'"
        ).fetchone()
        conn.close()
        assert stored["ra"] == 10.0  # first write is authoritative


class TestIdempotencyAndDeterminism:
    def test_reingestion_skips_everything(self, tmp_path):
        rows = [make_row(i) for i in range(8001, 8004)]
        pipe, first = run_pipeline(tmp_path, csv_bytes(rows))
        assert first.rows_inserted == 3
        before = table_checksum(str(tmp_path / "gaia.db"))
        second = pipe.ingest()
        assert second.rows_inserted == 0
        assert second.rows_skipped == 3
        assert second.status == "COMPLETED"
        assert table_checksum(str(tmp_path / "gaia.db")) == before

    def test_deterministic_across_databases(self, tmp_path):
        rows = [make_row(i) for i in range(8101, 8106)]
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        _, r1 = run_pipeline(tmp_path / "a", csv_bytes(rows))
        _, r2 = run_pipeline(tmp_path / "b", csv_bytes(rows))
        assert table_checksum(str(tmp_path / "a" / "gaia.db")) == table_checksum(
            str(tmp_path / "b" / "gaia.db")
        )
        assert r1.rows_inserted == r2.rows_inserted == 5

    def test_reconciliation_attack_never_overwrites(self, tmp_path):
        """Ingest, then 're-ingest' corrupted values under the same keys."""
        good = [make_row(i, ra="12.5") for i in range(8201, 8204)]
        run_pipeline(tmp_path, csv_bytes(good))
        before = table_checksum(str(tmp_path / "gaia.db"))

        corrupted = [make_row(i, ra="99.9", parallax="0.01") for i in range(8201, 8204)]
        _, second = run_pipeline(tmp_path, csv_bytes(corrupted))
        assert second.status == "COMPLETED"
        assert second.rows_inserted == 0
        assert second.rows_skipped == 3
        assert table_checksum(str(tmp_path / "gaia.db")) == before

    def test_manifest_records_query_and_params(self, tmp_path):
        spec = GaiaQuerySpec(min_parallax_mas=MIN_PARALLAX_MAS_2000LY)
        _, result = run_pipeline(tmp_path, csv_bytes([make_row(8301)]), spec=spec)
        conn = connect(str(tmp_path / "gaia.db"))
        manifest = conn.execute(
            "SELECT adql, adql_hash, params_json, status FROM ingestion_manifest "
            "WHERE run_id = ?",
            (result.run_id,),
        ).fetchone()
        conn.close()
        expected_adql = build_adql(spec)
        assert manifest["adql"] == expected_adql
        assert manifest["adql_hash"] == query_hash(expected_adql)
        assert "parallax >= 1.63078" in manifest["adql"]
        params = __import__("json").loads(manifest["params_json"])
        assert params["min_parallax_mas"] == MIN_PARALLAX_MAS_2000LY
        assert manifest["status"] == "COMPLETED"

    def test_run_ids_unique_per_run(self, tmp_path):
        pipe, first = run_pipeline(tmp_path, csv_bytes([make_row(8401)]))
        second = pipe.ingest()
        assert first.run_id != second.run_id


# ---------------------------------------------------------------------------
# Loud-failure contract
# ---------------------------------------------------------------------------

class TestLoudFailures:
    def test_tap_error_payload_is_contract_error(self, tmp_path):
        pipe = GaiaDR3IngestionPipeline(
            str(tmp_path / "gaia.db"),
            FakeTransport("ERROR: ADQL parse error near 'FORM'\n"),
        )
        with pytest.raises(IngestionContractError):
            pipe.ingest()
        conn = connect(str(tmp_path / "gaia.db"))
        count = conn.execute("SELECT COUNT(*) AS n FROM stars_astrometry").fetchone()["n"]
        status = conn.execute(
            "SELECT status FROM ingestion_manifest"
        ).fetchone()["status"]
        conn.close()
        assert count == 0  # never a silent empty "success"
        assert status == "FAILED"

    def test_empty_body_is_contract_error(self, tmp_path):
        pipe = GaiaDR3IngestionPipeline(
            str(tmp_path / "gaia.db"), FakeTransport("")
        )
        with pytest.raises(IngestionContractError):
            pipe.ingest()

    def test_header_missing_column_is_contract_error(self, tmp_path):
        short_header = [c for c in COLUMN_NAMES if c != "ruwe"]
        payload = csv_bytes([make_row(8501)], header=short_header)
        pipe = GaiaDR3IngestionPipeline(str(tmp_path / "gaia.db"), FakeTransport(payload))
        with pytest.raises(IngestionContractError, match="header"):
            pipe.ingest()

    def test_header_extra_column_is_contract_error(self, tmp_path):
        payload = csv_bytes(
            [make_row(8511)], header=list(COLUMN_NAMES) + ["surprise"]
        )
        pipe = GaiaDR3IngestionPipeline(str(tmp_path / "gaia.db"), FakeTransport(payload))
        with pytest.raises(IngestionContractError):
            pipe.ingest()

    def test_empty_result_is_a_legitimate_success(self, tmp_path):
        _, result = run_pipeline(tmp_path, csv_bytes([]))
        assert result.status == "COMPLETED"
        assert result.rows_inserted == 0
        assert result.rows_rejected == 0

    def test_malformed_rows_counted_never_stored(self, tmp_path):
        rows = [
            make_row(8601),
            make_row(8602, ra="not-a-number"),
            make_row(8603, parallax="nan"),
            make_row(8604),
        ]
        _, result = run_pipeline(tmp_path, csv_bytes(rows))
        assert result.status == "COMPLETED"
        assert result.rows_inserted == 2
        assert result.rows_rejected == 2
        conn = connect(str(tmp_path / "gaia.db"))
        ids = {
            r["source_id"]
            for r in conn.execute("SELECT source_id FROM stars_astrometry")
        }
        conn.close()
        assert ids == {"8601", "8604"}

    def test_short_row_counted_rejected(self, tmp_path):
        good = make_row(8611)
        short = list(good[c] for c in COLUMN_NAMES)[:-3]
        _, result = run_pipeline(tmp_path, csv_bytes([good, short]))
        assert result.rows_inserted == 1
        assert result.rows_rejected == 1

    def test_long_row_counted_rejected(self, tmp_path):
        good = make_row(8621)
        long_row = list(good[c] for c in COLUMN_NAMES) + ["extra"]
        _, result = run_pipeline(tmp_path, csv_bytes([good, long_row]))
        assert result.rows_inserted == 1
        assert result.rows_rejected == 1

    def test_circuit_breaker_trips(self, tmp_path):
        rows = [make_row(8700 + i) for i in range(150)]
        rows[9] = make_row(8709, ra="bogus")    # 1st bad: 1/100 == threshold -> survives
        rows[119] = make_row(8819, dec="NaN")   # 2nd bad: 2/120 > threshold -> trip
        pipe = GaiaDR3IngestionPipeline(
            str(tmp_path / "gaia.db"),
            FakeTransport(csv_bytes(rows)),
            batch_size=50,
            rejection_threshold=0.01,
            rejection_min_rows=100,
        )
        with pytest.raises(IngestionContractError, match="circuit breaker"):
            pipe.ingest()
        conn = connect(str(tmp_path / "gaia.db"))
        status = conn.execute(
            "SELECT status FROM ingestion_manifest ORDER BY run_id"
        ).fetchall()[-1]["status"]
        inserted = conn.execute(
            "SELECT COUNT(*) AS n FROM stars_astrometry"
        ).fetchone()["n"]
        conn.close()
        assert status == "FAILED"
        # both 50-row batches committed before the trip; nothing after
        assert inserted == 100

    def test_breaker_below_min_rows_does_not_trip(self, tmp_path):
        rows = [make_row(8800 + i) for i in range(50)]
        rows[3] = make_row(8803, ra="x")
        rows[13] = make_row(8813, ra="y")
        rows[23] = make_row(8823, ra="z")
        _, result = run_pipeline(tmp_path, csv_bytes(rows), rejection_min_rows=100)
        assert result.status == "COMPLETED"
        assert result.rows_rejected == 3
        assert result.rows_inserted == 47

    def test_breaker_disabled_at_threshold_one(self, tmp_path):
        rows = [make_row(8900 + i) for i in range(150)]
        for i in (5, 50, 120):
            rows[i] = make_row(8900 + i, ra="bad")
        _, result = run_pipeline(
            tmp_path, csv_bytes(rows), rejection_threshold=1.0
        )
        assert result.status == "COMPLETED"
        assert result.rows_rejected == 3
        assert result.rows_inserted == 147

    def test_invalid_constructor_arguments(self, tmp_path):
        with pytest.raises(IngestionContractError):
            GaiaDR3IngestionPipeline(str(tmp_path / "d.db"), batch_size=0)
        with pytest.raises(IngestionContractError):
            GaiaDR3IngestionPipeline(str(tmp_path / "d.db"), rejection_threshold=0.0)
        with pytest.raises(IngestionContractError):
            GaiaDR3IngestionPipeline(str(tmp_path / "d.db"), rejection_threshold=1.5)


# ---------------------------------------------------------------------------
# Failure, interruption, recovery
# ---------------------------------------------------------------------------

class TestInterruptionAndRecovery:
    def test_network_failure_at_start(self, tmp_path):
        pipe = GaiaDR3IngestionPipeline(
            str(tmp_path / "gaia.db"),
            FakeTransport(csv_bytes([make_row(9001)]), fail_on_sync=True),
        )
        with pytest.raises(TransportError):
            pipe.ingest()
        conn = connect(str(tmp_path / "gaia.db"))
        status = conn.execute("SELECT status FROM ingestion_manifest").fetchone()["status"]
        count = conn.execute("SELECT COUNT(*) AS n FROM stars_astrometry").fetchone()["n"]
        conn.close()
        assert status == "FAILED"
        assert count == 0

    def test_interrupted_midstream_persists_committed_batches(self, tmp_path):
        rows = [make_row(9100 + i) for i in range(5)]
        payload = csv_bytes(rows)  # header + 5 lines
        pipe = GaiaDR3IngestionPipeline(
            str(tmp_path / "gaia.db"),
            FakeTransport(payload, fail_after_lines=4),  # header + 3 rows, then die
            batch_size=2,
        )
        with pytest.raises(TransportError):
            pipe.ingest()
        conn = connect(str(tmp_path / "gaia.db"))
        status = conn.execute(
            "SELECT status FROM ingestion_manifest ORDER BY run_id"
        ).fetchall()[-1]["status"]
        inserted = conn.execute(
            "SELECT COUNT(*) AS n FROM stars_astrometry"
        ).fetchone()["n"]
        conn.close()
        assert status == "FAILED"
        assert inserted == 2  # exactly the first committed batch

    def test_rerun_after_interruption_completes_idempotently(self, tmp_path):
        rows = [make_row(9200 + i) for i in range(5)]
        payload = csv_bytes(rows)
        broken = GaiaDR3IngestionPipeline(
            str(tmp_path / "gaia.db"),
            FakeTransport(payload, fail_after_lines=3),
            batch_size=2,
        )
        with pytest.raises(TransportError):
            broken.ingest()

        recovered = GaiaDR3IngestionPipeline(
            str(tmp_path / "gaia.db"), FakeTransport(payload), batch_size=2
        )
        result = recovered.ingest()
        assert result.status == "COMPLETED"
        assert result.rows_inserted == 3  # the 2 stored rows are skipped
        assert result.rows_skipped == 2
        conn = connect(str(tmp_path / "gaia.db"))
        total = conn.execute("SELECT COUNT(*) AS n FROM stars_astrometry").fetchone()["n"]
        statuses = [
            r["status"]
            for r in conn.execute(
                "SELECT status FROM ingestion_manifest ORDER BY run_id"
            )
        ]
        conn.close()
        assert total == 5
        assert statuses == ["FAILED", "COMPLETED"]

    def test_result_is_frozen(self, tmp_path):
        _, result = run_pipeline(tmp_path, csv_bytes([make_row(9301)]))
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.rows_inserted = 999


# ---------------------------------------------------------------------------
# Asynchronous UWS path
# ---------------------------------------------------------------------------

class TestUwsAsync:
    def test_async_happy_path(self, tmp_path):
        transport = FakeTransport(
            csv_bytes([make_row(9401)]), phases=["RUN", "COMPLETED"]
        )
        pipe = GaiaDR3IngestionPipeline(
            str(tmp_path / "gaia.db"),
            transport,
            use_async=True,
            poll_interval_s=0.0,
        )
        result = pipe.ingest()
        assert result.status == "COMPLETED"
        assert result.rows_inserted == 1
        assert transport.job_queries == [build_adql(pipe.spec)]
        assert transport.job_phase_sets == ["RUN"]

    def test_async_error_phase_is_loud(self, tmp_path):
        transport = FakeTransport(
            csv_bytes([make_row(9411)]), phases=["ERROR"]
        )
        pipe = GaiaDR3IngestionPipeline(
            str(tmp_path / "gaia.db"),
            transport,
            use_async=True,
            poll_interval_s=0.0,
        )
        with pytest.raises(TransportError, match="ERROR"):
            pipe.ingest()

    def test_async_timeout_is_loud(self, tmp_path):
        transport = FakeTransport(
            csv_bytes([make_row(9421)]), phases=["EXECUTING"]
        )
        pipe = GaiaDR3IngestionPipeline(
            str(tmp_path / "gaia.db"),
            transport,
            use_async=True,
            poll_interval_s=0.0,
            max_wait_s=0.0,
        )
        with pytest.raises(TransportError, match="max wait"):
            pipe.ingest()

    def test_async_aborted_phase_is_loud(self, tmp_path):
        transport = FakeTransport(
            csv_bytes([make_row(9431)]), phases=["ABORTED"]
        )
        pipe = GaiaDR3IngestionPipeline(
            str(tmp_path / "gaia.db"),
            transport,
            use_async=True,
            poll_interval_s=0.0,
        )
        with pytest.raises(TransportError, match="ABORTED"):
            pipe.ingest()
