"""SQLite layer tests: schema, conflict policy, transactions, manifest, WAL."""

import threading
import time

import pytest

from astra.ingestion import (
    COLUMN_NAMES,
    INSERT_SQL,
    IngestionManifest,
    connect,
    ensure_schema,
    insert_batch,
)
from astra.ingestion.exceptions import IngestionError, IngestionRunError
from test_ingestion_pipeline import make_row
from test_ingestion_validation import make_record


class TestSchema:
    def test_ensure_schema_is_idempotent(self, tmp_path):
        db = str(tmp_path / "s.db")
        conn = connect(db)
        ensure_schema(conn)
        ensure_schema(conn)  # second call must be a no-op
        names = {
            r["name"]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        conn.close()
        assert {"stars_astrometry", "ingestion_manifest"} <= names

    def test_indexes_exist(self, tmp_path):
        db = str(tmp_path / "s.db")
        conn = connect(db)
        ensure_schema(conn)
        names = {
            r["name"]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            )
        }
        conn.close()
        assert {"idx_gaia_ra_dec", "idx_gaia_parallax"} <= names

    def test_table_columns_match_canonical_order(self, tmp_path):
        db = str(tmp_path / "s.db")
        conn = connect(db)
        ensure_schema(conn)
        info = conn.execute("PRAGMA table_info(stars_astrometry)").fetchall()
        conn.close()
        names = [r["name"] for r in info]
        assert names == list(COLUMN_NAMES) + ["data_classification"]

    def test_source_id_is_primary_key(self, tmp_path):
        db = str(tmp_path / "s.db")
        conn = connect(db)
        ensure_schema(conn)
        info = conn.execute("PRAGMA table_info(stars_astrometry)").fetchall()
        conn.close()
        pk = {r["name"]: r["pk"] for r in info}
        assert pk["source_id"] == 1
        assert all(v == 0 for k, v in pk.items() if k != "source_id")

    def test_coordinates_are_not_null_enforced(self, tmp_path):
        db = str(tmp_path / "s.db")
        conn = connect(db)
        ensure_schema(conn)
        info = conn.execute("PRAGMA table_info(stars_astrometry)").fetchall()
        notnull = {r["name"]: r["notnull"] for r in info}
        conn.close()
        assert notnull["ra"] == 1 and notnull["dec"] == 1
        assert notnull["parallax"] == 0  # optional columns stay nullable

    def test_wal_journal_mode(self, tmp_path):
        db = str(tmp_path / "s.db")
        conn = connect(db)
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()
        assert mode.lower() == "wal"

    def test_row_factory_is_sqlite_row(self, tmp_path):
        conn = connect(str(tmp_path / "s.db"))
        value = conn.execute("SELECT 1 AS x").fetchone()["x"]
        conn.close()
        assert value == 1


class TestConflictPolicy:
    def test_insert_sql_uses_do_nothing(self):
        assert "ON CONFLICT(source_id) DO NOTHING" in INSERT_SQL
        assert "INSERT OR REPLACE" not in INSERT_SQL

    def test_insert_batch_counts(self, tmp_path):
        conn = connect(str(tmp_path / "c.db"))
        ensure_schema(conn)
        inserted, skipped = insert_batch(
            conn, [make_record("101"), make_record("102")]
        )
        conn.close()
        assert (inserted, skipped) == (2, 0)

    def test_duplicate_skipped(self, tmp_path):
        conn = connect(str(tmp_path / "c.db"))
        ensure_schema(conn)
        insert_batch(conn, [make_record("201")])
        inserted, skipped = insert_batch(conn, [make_record("201")])
        conn.close()
        assert (inserted, skipped) == (0, 1)

    def test_conflicting_duplicate_never_overwrites_authority(self, tmp_path):
        """A different measurement under the same key must NOT replace it."""
        conn = connect(str(tmp_path / "c.db"))
        ensure_schema(conn)
        original = make_record("301", ra=12.5, parallax=1.9)
        insert_batch(conn, [original])
        impostor = make_record("301", ra=99.9, parallax=0.01)
        inserted, skipped = insert_batch(conn, [impostor])
        stored = conn.execute(
            "SELECT ra, parallax FROM stars_astrometry WHERE source_id = '301'"
        ).fetchone()
        conn.close()
        assert (inserted, skipped) == (0, 1)
        assert stored["ra"] == 12.5
        assert stored["parallax"] == 1.9

    def test_empty_batch_is_a_noop(self, tmp_path):
        conn = connect(str(tmp_path / "c.db"))
        ensure_schema(conn)
        assert insert_batch(conn, []) == (0, 0)
        conn.close()


class TestTransactionSafety:
    def test_batch_is_all_or_nothing(self, tmp_path):
        conn = connect(str(tmp_path / "t.db"))
        ensure_schema(conn)
        poisoned = make_record("401")
        object.__setattr__(poisoned, "ra", None)  # simulate a storage-layer fault
        good = make_record("402")
        with pytest.raises(IngestionError, match="rolled back"):
            insert_batch(conn, [good, poisoned, make_record("403")])
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM stars_astrometry"
        ).fetchone()["n"]
        conn.close()
        assert count == 0  # zero partial rows

    def test_connection_usable_after_rollback(self, tmp_path):
        conn = connect(str(tmp_path / "t.db"))
        ensure_schema(conn)
        poisoned = make_record("501")
        object.__setattr__(poisoned, "dec", None)
        with pytest.raises(IngestionError):
            insert_batch(conn, [poisoned])
        inserted, _ = insert_batch(conn, [make_record("502")])
        conn.close()
        assert inserted == 1

    def test_error_is_wrapped_as_ingestion_error(self, tmp_path):
        conn = connect(str(tmp_path / "t.db"))
        ensure_schema(conn)
        poisoned = make_record("601")
        object.__setattr__(poisoned, "ra", None)
        with pytest.raises(IngestionError) as excinfo:
            insert_batch(conn, [poisoned])
        conn.close()
        assert excinfo.value.details["batch_size"] == 1


class TestConcurrency:
    def test_second_writer_waits_for_lock(self, tmp_path):
        """WAL + busy timeout: a competing writer waits, then succeeds."""
        import sqlite3

        db = str(tmp_path / "w.db")
        # Writer A is held across a helper thread, so allow cross-thread use
        # (production connect() keeps the sqlite3 default; this is test-only).
        writer_a = sqlite3.connect(db, isolation_level=None, check_same_thread=False)
        writer_a.row_factory = sqlite3.Row
        ensure_schema(writer_a)
        writer_b = connect(db)
        ensure_schema(writer_b)

        writer_a.execute("BEGIN IMMEDIATE")
        writer_a.execute(
            INSERT_SQL, make_record("701").to_db_tuple()
        )
        releaser = threading.Timer(0.3, lambda: writer_a.execute("COMMIT"))
        releaser.start()

        started = time.monotonic()
        inserted, _ = insert_batch(writer_b, [make_record("702")])
        elapsed = time.monotonic() - started
        releaser.join()
        total = writer_a.execute(
            "SELECT COUNT(*) AS n FROM stars_astrometry"
        ).fetchone()["n"]
        writer_a.close()
        writer_b.close()
        assert inserted == 1
        assert elapsed >= 0.2  # it genuinely waited for the lock
        assert total == 2


class TestManifest:
    def test_lifecycle(self, tmp_path):
        conn = connect(str(tmp_path / "m.db"))
        ensure_schema(conn)
        manifest = IngestionManifest.begin(
            conn, "run-1", "SELECT 1", "hash-1", {"k": 1}
        )
        row = manifest.row()
        assert row["status"] == "RUNNING"
        manifest.bump(inserted=5, skipped=2, rejected=1, batches=1)
        manifest.bump(inserted=3, batches=1)
        manifest.set_status("COMPLETED")
        final = manifest.row()
        conn.close()
        assert final["rows_inserted"] == 8
        assert final["rows_skipped"] == 2
        assert final["rows_rejected"] == 1
        assert final["batches_committed"] == 2
        assert final["status"] == "COMPLETED"

    def test_failure_text_recorded(self, tmp_path):
        conn = connect(str(tmp_path / "m.db"))
        ensure_schema(conn)
        manifest = IngestionManifest.begin(conn, "run-2", "Q", "h", {})
        manifest.set_status("FAILED", failure="network unreachable")
        row = manifest.row()
        conn.close()
        assert row["status"] == "FAILED"
        assert row["failure"] == "network unreachable"

    def test_get_and_exists(self, tmp_path):
        conn = connect(str(tmp_path / "m.db"))
        ensure_schema(conn)
        IngestionManifest.begin(conn, "run-3", "Q", "h", {})
        assert IngestionManifest.exists(conn, "run-3")
        assert not IngestionManifest.exists(conn, "run-999")
        fetched = IngestionManifest.get(conn, "run-3")
        conn.close()
        assert fetched["run_id"] == "run-3"

    def test_get_unknown_row_raises_on_row_access(self, tmp_path):
        conn = connect(str(tmp_path / "m.db"))
        ensure_schema(conn)
        manifest = IngestionManifest(conn, "ghost")
        with pytest.raises(IngestionRunError):
            manifest.row()
        conn.close()

    def test_started_and_updated_stamps_present(self, tmp_path):
        conn = connect(str(tmp_path / "m.db"))
        ensure_schema(conn)
        manifest = IngestionManifest.begin(conn, "run-4", "Q", "h", {})
        row = manifest.row()
        conn.close()
        assert row["started_utc"]
        assert row["updated_utc"]
