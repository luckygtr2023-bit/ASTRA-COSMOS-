"""SQLite storage: connection policy, conflict-safe inserts, run manifest.

SAFETY CONTRACT
    - Inserts use ``ON CONFLICT(source_id) DO NOTHING``: an authoritative
      row is NEVER silently overwritten. Re-ingesting the same source
      skips existing rows and counts them (``rows_skipped``). Different
      data under an existing ``source_id`` is skipped too — reconciliation
      of conflicting measurements is an explicit, future, audited process,
      not an accidental side effect of ingestion.
    - Every batch is one explicit transaction; any failure rolls back the
      ENTIRE batch (zero partial rows) and raises ``IngestionError``.
    - Connections run WAL journal mode with a 30 s busy timeout so a second
      writer waits for the lock instead of crashing ("database is locked").
    - ``ingestion_manifest`` is the run ledger: canonical ADQL, its sha256,
      query parameters, live counters, status (RUNNING/COMPLETED/FAILED)
      and failure text. Manifest rows are provenance METADATA, so UTC
      wall-clock stamps are appropriate here (unlike simulation state,
      which never reads the wall clock). Table content itself is never
      timestamped, so identical inputs produce identical tables.

RESUME SEMANTICS (honest scope)
    A TAP sync response is a forward-only stream: an interrupted run cannot
    seek to its crash point. What IS guaranteed: batches already committed
    persist; the failing batch rolls back whole; the manifest records the
    failure; and re-running the identical query is idempotent (existing
    source_ids are skipped). True mid-stream resumability requires
    partitioned retrieval (e.g. HEALPix chunks / UWS jobs per chunk) and
    remains documented remaining work — restart-idempotence is NOT claimed
    to be resume-from-watermark.
"""

import json
import sqlite3
from datetime import datetime, timezone
from typing import Iterable, Optional, Sequence

from astra.ingestion.exceptions import IngestionError, IngestionRunError
from astra.ingestion.schema import (
    COLUMN_NAMES,
    DDL_INDEXES,
    DDL_MANIFEST,
    DDL_SOURCES_REGISTRY,
    DDL_STARS_ASTROMETRY,
)
from astra.ingestion.validate import GaiaRecord

#: Seconds a writer waits for a competing lock before failing.
BUSY_TIMEOUT_S = 30.0

STATUS_RUNNING = "RUNNING"
STATUS_COMPLETED = "COMPLETED"
STATUS_FAILED = "FAILED"

_INSERT_COLUMNS = tuple(COLUMN_NAMES) + ("data_classification",)

INSERT_SQL = (
    f"INSERT INTO stars_astrometry ({', '.join(_INSERT_COLUMNS)}) "
    f"VALUES ({', '.join('?' * len(_INSERT_COLUMNS))}) "
    "ON CONFLICT(source_id) DO NOTHING"
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db_path: str) -> sqlite3.Connection:
    """Open a WAL connection in explicit-transaction mode with busy timeout."""
    conn = sqlite3.connect(db_path, timeout=BUSY_TIMEOUT_S, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(f"PRAGMA busy_timeout = {int(BUSY_TIMEOUT_S * 1000)}")
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create tables and supporting indexes if absent (idempotent)."""
    conn.execute(DDL_STARS_ASTROMETRY)
    conn.execute(DDL_MANIFEST)
    conn.execute(DDL_SOURCES_REGISTRY)
    for ddl in DDL_INDEXES:
        conn.execute(ddl)


def register_source(
    conn: sqlite3.Connection,
    metadata: dict,
    *,
    registered_utc: Optional[str] = None,
) -> None:
    """Register (or idempotently refresh) catalog-source metadata.

    ``sources_registry`` records HOW a catalog's data was obtained: endpoint,
    protocol, reference frame, reference epoch, and the provenance defaults
    that apply to its columns. This is pipeline-owned configuration, so
    re-registration UPDATES the row (last-writer-wins on our own metadata) —
    it never touches ``stars_astrometry`` measurements.
    """
    required = (
        "source_name", "title", "endpoint_url", "protocol",
        "reference_frame", "ref_epoch", "data_classification_default",
        "derived_columns",
    )
    missing = [key for key in required if key not in metadata]
    if missing:
        raise IngestionError(
            "source metadata is missing required keys",
            {"missing": missing},
        )
    now = registered_utc or _utc_now()
    conn.execute(
        "INSERT INTO sources_registry "
        "(source_name, title, endpoint_url, protocol, reference_frame, ref_epoch, "
        "data_classification_default, derived_columns, first_registered_utc, "
        "updated_utc) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(source_name) DO UPDATE SET "
        "title = excluded.title, endpoint_url = excluded.endpoint_url, "
        "protocol = excluded.protocol, reference_frame = excluded.reference_frame, "
        "ref_epoch = excluded.ref_epoch, "
        "data_classification_default = excluded.data_classification_default, "
        "derived_columns = excluded.derived_columns, updated_utc = excluded.updated_utc",
        (
            metadata["source_name"],
            metadata["title"],
            metadata["endpoint_url"],
            metadata["protocol"],
            metadata["reference_frame"],
            float(metadata["ref_epoch"]),
            metadata["data_classification_default"],
            json.dumps(list(metadata["derived_columns"])),
            now,
            now,
        ),
    )


def get_source(
    conn: sqlite3.Connection, source_name: str
) -> Optional[sqlite3.Row]:
    """Return the registry row for ``source_name`` or None."""
    cur = conn.execute(
        "SELECT * FROM sources_registry WHERE source_name = ?", (source_name,)
    )
    return cur.fetchone()


def insert_batch(
    conn: sqlite3.Connection, records: Sequence[GaiaRecord]
) -> tuple[int, int]:
    """Insert one batch in a single transaction; return (inserted, skipped).

    Conflict policy: DO NOTHING. An existing authoritative row is never
    replaced; the incoming duplicate is counted as skipped. On any sqlite
    error the whole batch is rolled back and ``IngestionError`` raised.
    """
    if not records:
        return 0, 0
    before = conn.total_changes
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.executemany(INSERT_SQL, [r.to_db_tuple() for r in records])
        conn.execute("COMMIT")
    except sqlite3.Error as exc:
        conn.execute("ROLLBACK")
        raise IngestionError(
            f"batch insert failed; rolled back {len(records)} rows",
            {"batch_size": len(records), "sqlite": str(exc)},
        ) from exc
    inserted = conn.total_changes - before
    return inserted, len(records) - inserted


class IngestionManifest:
    """Handle on one ingestion-run row of ``ingestion_manifest``."""

    def __init__(self, conn: sqlite3.Connection, run_id: str):
        self._conn = conn
        self.run_id = run_id

    @classmethod
    def begin(
        cls,
        conn: sqlite3.Connection,
        run_id: str,
        adql: str,
        adql_hash: str,
        params: dict,
    ) -> "IngestionManifest":
        now = _utc_now()
        conn.execute(
            "INSERT INTO ingestion_manifest "
            "(run_id, adql_hash, adql, params_json, status, started_utc, updated_utc) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                adql_hash,
                adql,
                json.dumps(params, sort_keys=True),
                STATUS_RUNNING,
                now,
                now,
            ),
        )
        return cls(conn, run_id)

    @staticmethod
    def get(conn: sqlite3.Connection, run_id: str) -> Optional[sqlite3.Row]:
        cur = conn.execute(
            "SELECT * FROM ingestion_manifest WHERE run_id = ?", (run_id,)
        )
        return cur.fetchone()

    @staticmethod
    def exists(conn: sqlite3.Connection, run_id: str) -> bool:
        return IngestionManifest.get(conn, run_id) is not None

    def bump(
        self,
        *,
        inserted: int = 0,
        skipped: int = 0,
        rejected: int = 0,
        batches: int = 0,
    ) -> None:
        """Accumulate counters (committed immediately; survives failure)."""
        self._conn.execute(
            "UPDATE ingestion_manifest SET rows_inserted = rows_inserted + ?, "
            "rows_skipped = rows_skipped + ?, rows_rejected = rows_rejected + ?, "
            "batches_committed = batches_committed + ?, updated_utc = ? "
            "WHERE run_id = ?",
            (inserted, skipped, rejected, batches, _utc_now(), self.run_id),
        )

    def set_status(self, status: str, failure: Optional[str] = None) -> None:
        self._conn.execute(
            "UPDATE ingestion_manifest SET status = ?, failure = ?, updated_utc = ? "
            "WHERE run_id = ?",
            (status, failure, _utc_now(), self.run_id),
        )

    def row(self) -> sqlite3.Row:
        found = IngestionManifest.get(self._conn, self.run_id)
        if found is None:
            raise IngestionRunError(
                "manifest row vanished", {"run_id": self.run_id}
            )
        return found
