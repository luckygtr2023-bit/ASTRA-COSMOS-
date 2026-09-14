"""Gaia DR3 ingestion pipeline: streaming validation -> safe batch inserts.

FLOW
    build ADQL (deterministic) -> hash -> open manifest run -> stream CSV
    lines from the transport (sync probe or UWS async) -> validate header
    (exact expected column set) -> validate each row (NULLs preserved,
    impossible values rejected and counted) -> conflict-safe batch inserts
    (ON CONFLICT DO NOTHING) -> manifest counters after every committed
    batch -> COMPLETED, or a loud failure that marks the run FAILED.

LOUD-FAILURE CONTRACT (nothing fails silently)
    - Response header must contain exactly the expected columns; anything
      else (including a TAP error payload like ``ERROR ...``) raises
      ``IngestionContractError``. An empty database is NEVER reported as a
      successful ingestion of a failed response.
    - Rejection circuit breaker: if malformed rows exceed
      ``rejection_threshold`` of seen rows once at least
      ``rejection_min_rows`` have been seen, the run is marked FAILED and
      ``IngestionContractError`` raised. Below the minimum, malformed rows
      are still counted but a small sample cannot trip the breaker.
    - Transport failures mark the run FAILED and re-raise
      ``TransportError``; batches already committed persist (see
      database.py for the honest resume semantics).

NO FABRICATION, NO GUESSES
    Missing values are stored as SQL NULL; malformed rows are rejected and
    counted; coordinates pass through unmodified (ICRS, as published);
    every ingested row carries ``data_classification = REAL_DATA`` for its
    measurements, with GSP-Phot columns flagged DERIVED_DATA in the schema
    catalog. This pipeline never generates or substitutes records.
"""

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterator, Optional

from astra.ingestion.database import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    IngestionManifest,
    connect,
    ensure_schema,
    insert_batch,
    register_source,
)
from astra.ingestion.exceptions import (
    IngestionContractError,
    IngestionError,
    MalformedRowError,
)
from astra.ingestion.query import GaiaQuerySpec, build_adql, query_hash
from astra.ingestion.schema import COLUMN_NAMES, GAIA_DR3_SOURCE_METADATA
from astra.ingestion.transport import TAP_BASE_URL, TapTransport, UrllibTapTransport, UwsAsyncClient
from astra.ingestion.validate import validate_row

DEFAULT_BATCH_SIZE = 10_000
DEFAULT_REJECTION_THRESHOLD = 0.01  # 1% of seen rows
DEFAULT_REJECTION_MIN_ROWS = 100


@dataclass(frozen=True)
class IngestionRunResult:
    """Immutable summary of one ingestion run (from the manifest ledger)."""

    run_id: str
    adql_hash: str
    status: str
    rows_inserted: int
    rows_skipped: int
    rows_rejected: int
    batches_committed: int


class GaiaDR3IngestionPipeline:
    """Stream Gaia DR3 TAP CSV into ``stars_astrometry`` safely."""

    def __init__(
        self,
        db_path: str,
        transport: Optional[TapTransport] = None,
        spec: Optional[GaiaQuerySpec] = None,
        *,
        batch_size: int = DEFAULT_BATCH_SIZE,
        rejection_threshold: float = DEFAULT_REJECTION_THRESHOLD,
        rejection_min_rows: int = DEFAULT_REJECTION_MIN_ROWS,
        use_async: bool = False,
        tap_base_url: str = TAP_BASE_URL,
        poll_interval_s: float = 5.0,
        max_wait_s: float = 90.0 * 60.0,
    ):
        if batch_size < 1:
            raise IngestionContractError(
                "batch_size must be >= 1", {"batch_size": batch_size}
            )
        if not (0.0 < rejection_threshold <= 1.0):
            raise IngestionContractError(
                "rejection_threshold must be in (0, 1]",
                {"rejection_threshold": rejection_threshold},
            )
        self.db_path = db_path
        self.spec = spec if spec is not None else GaiaQuerySpec()
        self.transport: TapTransport = (
            transport if transport is not None else UrllibTapTransport()
        )
        self.batch_size = batch_size
        self.rejection_threshold = rejection_threshold
        self.rejection_min_rows = rejection_min_rows
        self.use_async = use_async
        self.tap_base_url = tap_base_url
        self.poll_interval_s = poll_interval_s
        self.max_wait_s = max_wait_s

    # -- public API ---------------------------------------------------------

    def ingest(self) -> IngestionRunResult:
        """Run one ingestion attempt; always leaves a manifest record."""
        adql = build_adql(self.spec)
        adql_hash = query_hash(adql)
        params = {
            "parallax_over_error": self.spec.parallax_over_error,
            "max_ruwe": self.spec.max_ruwe,
            "min_parallax_mas": self.spec.min_parallax_mas,
            "columns": list(self.spec.columns),
        }
        conn = connect(self.db_path)
        try:
            ensure_schema(conn)
            # Idempotent catalog-source metadata registration (endpoint,
            # protocol, ICRS frame, J2016.0 epoch, provenance defaults).
            register_source(conn, GAIA_DR3_SOURCE_METADATA)
            manifest = IngestionManifest.begin(
                conn,
                self._new_run_id(conn, adql_hash),
                adql,
                adql_hash,
                params,
            )
            try:
                rejected_pending = self._stream_into(conn, manifest, adql)
            except (IngestionError, csv.Error, UnicodeDecodeError) as exc:
                manifest.set_status(STATUS_FAILED, failure=str(exc))
                raise
            manifest.bump(rejected=rejected_pending)
            manifest.set_status(STATUS_COMPLETED)
            row = manifest.row()
            return IngestionRunResult(
                run_id=manifest.run_id,
                adql_hash=row["adql_hash"],
                status=row["status"],
                rows_inserted=row["rows_inserted"],
                rows_skipped=row["rows_skipped"],
                rows_rejected=row["rows_rejected"],
                batches_committed=row["batches_committed"],
            )
        finally:
            conn.close()

    # -- internals ----------------------------------------------------------

    def _new_run_id(self, conn, adql_hash: str) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        base = f"gaia-dr3-{adql_hash[:12]}-{stamp}"
        if not IngestionManifest.exists(conn, base):
            return base
        suffix = 2
        while IngestionManifest.exists(conn, f"{base}-{suffix}"):
            suffix += 1
        return f"{base}-{suffix}"

    def _open_stream(self, adql: str) -> Iterator[bytes]:
        if self.use_async:
            client = UwsAsyncClient(
                self.transport,
                base_url=self.tap_base_url,
                poll_interval_s=self.poll_interval_s,
                max_wait_s=self.max_wait_s,
            )
            return client.stream_adql(adql)
        payload = {
            "REQUEST": "doQuery",
            "LANG": "ADQL",
            "FORMAT": "csv",
            "QUERY": adql,
        }
        return self.transport.post_sync(self.tap_base_url, payload)

    def _stream_into(self, conn, manifest: IngestionManifest, adql: str) -> int:
        """Stream the whole response; return rejected rows not yet flushed."""
        raw_lines = self._open_stream(adql)
        text_lines = (line.decode("utf-8") for line in raw_lines)
        rows = csv.reader(text_lines)

        header = next(rows, None)
        if header is None:
            raise IngestionContractError(
                "TAP response is empty (no header row)",
                {"expected_columns": list(COLUMN_NAMES)},
            )
        if header != list(COLUMN_NAMES):
            raise IngestionContractError(
                "TAP response header does not match the expected column set",
                {"expected": list(COLUMN_NAMES), "received": header},
            )

        batch: list = []
        rejected_pending = 0
        seen = 0
        rejected = 0
        for raw in rows:
            if not raw:  # physical blank line, not a data row
                continue
            seen += 1
            if len(raw) != len(header):
                rejected += 1
                rejected_pending += 1
            else:
                try:
                    batch.append(validate_row(dict(zip(header, raw))))
                except MalformedRowError:
                    rejected += 1
                    rejected_pending += 1
            if len(batch) >= self.batch_size:
                inserted, skipped = insert_batch(conn, batch)
                manifest.bump(
                    inserted=inserted, skipped=skipped, batches=1,
                    rejected=rejected_pending,
                )
                batch = []
                rejected_pending = 0
            if (
                seen >= self.rejection_min_rows
                and rejected / seen > self.rejection_threshold
            ):
                raise IngestionContractError(
                    "row-rejection circuit breaker tripped",
                    {"seen": seen, "rejected": rejected,
                     "threshold": self.rejection_threshold},
                )
        if batch:
            inserted, skipped = insert_batch(conn, batch)
            manifest.bump(
                inserted=inserted, skipped=skipped, batches=1,
                rejected=rejected_pending,
            )
            rejected_pending = 0
        return rejected_pending
