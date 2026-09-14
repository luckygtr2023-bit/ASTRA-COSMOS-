"""sources_registry tests: catalog-source metadata (endpoint, frame, epoch).

The registry records HOW ingested data was obtained — the ESA Gaia DR3 TAP
endpoint, the IVOA TAP/ADQL protocol, the ICRS reference frame, the J2016.0
reference epoch, and the provenance defaults. It is metadata, not data: no
catalog records live here.
"""

import json

import pytest

from astra.celestial.provenance import DataProvenance
from astra.ingestion import (
    COLUMN_NAMES,
    DERIVED_COLUMNS,
    GAIA_DR3_SOURCE_METADATA,
    GaiaDR3IngestionPipeline,
    TAP_BASE_URL,
    connect,
    ensure_schema,
    get_source,
    register_source,
)
from astra.ingestion.exceptions import IngestionError
from test_ingestion_pipeline import FakeTransport, csv_bytes, make_row, run_pipeline


def one_valid_row():
    return csv_bytes([make_row(9101)])


class TestRegistrySchema:
    def test_table_created_by_ensure_schema(self, tmp_path):
        conn = connect(str(tmp_path / "r.db"))
        ensure_schema(conn)
        names = {
            r["name"]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        conn.close()
        assert "sources_registry" in names

    def test_registry_columns(self, tmp_path):
        conn = connect(str(tmp_path / "r.db"))
        ensure_schema(conn)
        info = conn.execute("PRAGMA table_info(sources_registry)").fetchall()
        conn.close()
        assert [r["name"] for r in info] == [
            "source_name",
            "title",
            "endpoint_url",
            "protocol",
            "reference_frame",
            "ref_epoch",
            "data_classification_default",
            "derived_columns",
            "first_registered_utc",
            "updated_utc",
        ]


class TestGaiaDr3Metadata:
    def test_metadata_constant(self):
        meta = GAIA_DR3_SOURCE_METADATA
        assert meta["source_name"] == "gaia_dr3"
        assert meta["endpoint_url"] == TAP_BASE_URL
        assert meta["protocol"] == "IVOA TAP 1.1 / ADQL"
        assert meta["reference_frame"] == "ICRS"
        assert meta["ref_epoch"] == 2016.0  # Gaia DR3 reference epoch J2016.0
        assert meta["data_classification_default"] == "REAL_DATA"
        assert list(meta["derived_columns"]) == list(DERIVED_COLUMNS)

    def test_classification_default_is_a_real_provenance_value(self):
        value = GAIA_DR3_SOURCE_METADATA["data_classification_default"]
        assert DataProvenance(value) is DataProvenance.REAL_DATA

    def test_pipeline_registers_gaia_dr3_automatically(self, tmp_path):
        _, result = run_pipeline(tmp_path, one_valid_row())
        assert result.status == "COMPLETED"
        conn = connect(str(tmp_path / "gaia.db"))
        row = get_source(conn, "gaia_dr3")
        conn.close()
        assert row is not None
        assert row["title"] == "ESA Gaia DR3 (gaiadr3.gaia_source)"
        assert row["endpoint_url"] == "https://gea.esac.esa.int/tap-server/tap"
        assert row["protocol"] == "IVOA TAP 1.1 / ADQL"
        assert row["reference_frame"] == "ICRS"
        assert row["ref_epoch"] == pytest.approx(2016.0)
        assert row["data_classification_default"] == "REAL_DATA"
        assert json.loads(row["derived_columns"]) == list(DERIVED_COLUMNS)
        assert row["first_registered_utc"]
        assert row["updated_utc"]

    def test_registration_survives_failed_runs(self, tmp_path):
        """Even a FAILED run records which catalog produced the attempt."""
        broken = GaiaDR3IngestionPipeline(
            str(tmp_path / "gaia.db"), FakeTransport("ERROR: nope\n")
        )
        with pytest.raises(Exception):
            broken.ingest()
        conn = connect(str(tmp_path / "gaia.db"))
        row = get_source(conn, "gaia_dr3")
        conn.close()
        assert row is not None
        assert row["reference_frame"] == "ICRS"
        assert row["ref_epoch"] == pytest.approx(2016.0)


class TestRegistrySemantics:
    def test_reregistration_is_single_row(self, tmp_path):
        conn = connect(str(tmp_path / "r.db"))
        ensure_schema(conn)
        register_source(conn, dict(GAIA_DR3_SOURCE_METADATA), registered_utc="T1")
        first = get_source(conn, "gaia_dr3")
        assert first["first_registered_utc"] == "T1"
        register_source(conn, dict(GAIA_DR3_SOURCE_METADATA), registered_utc="T2")
        second = get_source(conn, "gaia_dr3")
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM sources_registry"
        ).fetchone()["n"]
        conn.close()
        assert count == 1
        assert second["first_registered_utc"] == "T1"  # history preserved
        assert second["updated_utc"] == "T2"

    def test_metadata_update_takes_effect(self, tmp_path):
        conn = connect(str(tmp_path / "r.db"))
        ensure_schema(conn)
        register_source(conn, dict(GAIA_DR3_SOURCE_METADATA))
        changed = dict(GAIA_DR3_SOURCE_METADATA)
        changed["title"] = "ESA Gaia DR3 (updated title)"
        register_source(conn, changed)
        row = get_source(conn, "gaia_dr3")
        conn.close()
        assert row["title"] == "ESA Gaia DR3 (updated title)"

    def test_get_unknown_source_returns_none(self, tmp_path):
        conn = connect(str(tmp_path / "r.db"))
        ensure_schema(conn)
        assert get_source(conn, "tycho-2") is None
        conn.close()

    def test_missing_metadata_keys_rejected(self, tmp_path):
        conn = connect(str(tmp_path / "r.db"))
        ensure_schema(conn)
        with pytest.raises(IngestionError, match="missing required keys"):
            register_source(conn, {"source_name": "incomplete"})
        conn.close()

    def test_measurements_table_untouched_by_registration(self, tmp_path):
        conn = connect(str(tmp_path / "r.db"))
        ensure_schema(conn)
        register_source(conn, dict(GAIA_DR3_SOURCE_METADATA))
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM stars_astrometry"
        ).fetchone()["n"]
        conn.close()
        assert count == 0

    def test_derived_flagging_partitions_the_canonical_columns(self, tmp_path):
        """Every canonical column is either measurement-REAL or flagged derived."""
        derived = set(DERIVED_COLUMNS)
        assert derived <= set(COLUMN_NAMES)
        assert "source_id" not in derived
        assert "ra" not in derived and "dec" not in derived
        assert "parallax" not in derived
        # and the DB row agrees with the module catalog
        _, _ = run_pipeline(tmp_path, one_valid_row())
        conn = connect(str(tmp_path / "gaia.db"))
        row = get_source(conn, "gaia_dr3")
        conn.close()
        assert set(json.loads(row["derived_columns"])) == derived
