"""sources_registry tests: catalog-source metadata (master archive section 3.1).

The registry records HOW ingested data was obtained - the four authoritative
repositories (ESA Gaia DR3, NASA Exoplanet Archive, SIMBAD, JPL Horizons)
with their endpoints, protocols, reference frames and epochs. It is metadata
and configuration, not data: no catalog records live here.
"""

import json

import pytest

from astra.celestial.provenance import DataProvenance
from astra.ingestion import (
    COLUMN_NAMES,
    GAIA_DR3_SOURCE_METADATA,
    GaiaDR3IngestionPipeline,
    MODEL_INFERRED_COLUMNS,
    TAP_BASE_URL,
    connect,
    ensure_schema,
    get_source,
    register_all_archive_sources,
    register_source,
    seed_pipeline_queries,
)
from astra.ingestion.exceptions import IngestionError
from test_ingestion_pipeline import FakeTransport, csv_bytes, make_row, run_pipeline


def one_valid_row():
    return csv_bytes([make_row(9101)])


class TestRegistrySchema:
    def test_all_seven_archive_tables_created(self, tmp_path):
        conn = connect(str(tmp_path / "r.db"))
        ensure_schema(conn)
        names = {
            r["name"]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        conn.close()
        assert {
            "stars_astrometry",
            "sources_registry",
            "astra_canonical_registry",
            "confirmed_exoplanets",
            "object_aliases_crossids",
            "pipeline_queries",
            "solar_system_bodies",
        } <= names
        assert "ingestion_manifest" in names  # pipeline addition

    def test_registry_columns(self, tmp_path):
        conn = connect(str(tmp_path / "r.db"))
        ensure_schema(conn)
        info = conn.execute("PRAGMA table_info(sources_registry)").fetchall()
        conn.close()
        assert [r["name"] for r in info] == [
            "source_key",
            "catalog_name",
            "provider",
            "release",
            "endpoint_url",
            "protocol",
            "reference_frame",
            "reference_epoch",
            "data_classification_default",
            "model_inferred_columns",
            "first_registered_utc",
            "updated_utc",
        ]


class TestGaiaDr3Metadata:
    def test_metadata_constant(self):
        meta = GAIA_DR3_SOURCE_METADATA
        assert meta["source_key"] == "GAIA_DR3"
        assert meta["catalog_name"] == "Gaia Data Release 3"
        assert meta["provider"] == "ESA ESAC"
        assert meta["release"] == "DR3"
        assert meta["endpoint_url"] == TAP_BASE_URL
        assert meta["protocol"] == "IVOA TAP / ADQL"
        assert meta["reference_frame"] == "ICRS"
        assert meta["reference_epoch"] == "J2016.0"  # archive section 3.1
        assert meta["data_classification_default"] == "REAL_DATA"
        assert list(meta["model_inferred_columns"]) == list(MODEL_INFERRED_COLUMNS)

    def test_classification_default_is_a_real_provenance_value(self):
        value = GAIA_DR3_SOURCE_METADATA["data_classification_default"]
        assert DataProvenance(value) is DataProvenance.REAL_DATA

    def test_pipeline_registers_all_four_archives(self, tmp_path):
        _, result = run_pipeline(tmp_path, one_valid_row())
        assert result.status == "COMPLETED"
        conn = connect(str(tmp_path / "gaia.db"))
        rows = {
            r["source_key"]: r
            for r in conn.execute("SELECT * FROM sources_registry")
        }
        conn.close()
        assert set(rows) == {"GAIA_DR3", "NEXSCI_PS", "SIMBAD", "JPL_HORIZONS"}
        gaia = rows["GAIA_DR3"]
        assert gaia["endpoint_url"] == "https://gea.esac.esa.int/tap-server/tap"
        assert gaia["protocol"] == "IVOA TAP / ADQL"
        assert gaia["reference_frame"] == "ICRS"
        assert gaia["reference_epoch"] == "J2016.0"
        assert json.loads(gaia["model_inferred_columns"]) == list(
            MODEL_INFERRED_COLUMNS
        )
        assert rows["NEXSCI_PS"]["reference_epoch"] == "J2000.0"
        assert rows["NEXSCI_PS"]["provider"] == "Caltech / NASA IPAC"
        assert rows["SIMBAD"]["endpoint_url"] == (
            "https://simbad.u-strasbg.fr/simbad/sim-tap/sync"
        )
        assert rows["JPL_HORIZONS"]["protocol"] == "REST API"
        assert rows["JPL_HORIZONS"]["reference_frame"] == "ICRF"
        assert rows["JPL_HORIZONS"]["reference_epoch"] == "Dynamic"

    def test_pipeline_seeds_pipeline_queries(self, tmp_path):
        run_pipeline(tmp_path, one_valid_row())
        conn = connect(str(tmp_path / "gaia.db"))
        rows = [
            dict(r)
            for r in conn.execute(
                "SELECT target_catalog, query_type, endpoint_url, query_body "
                "FROM pipeline_queries ORDER BY query_id"
            )
        ]
        # re-run must not duplicate
        seed_pipeline_queries(conn)
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM pipeline_queries"
        ).fetchone()["n"]
        conn.close()
        assert count == 4
        assert [r["target_catalog"] for r in rows] == [
            "Gaia DR3",
            "NASA Exoplanet Archive",
            "SIMBAD",
            "JPL Horizons",
        ]
        assert "parallax_over_error > 5" in rows[0]["query_body"]
        assert "default_flag=1" in rows[1]["query_body"]
        assert "JOIN ident" in rows[2]["query_body"]
        assert "COMMAND='499'" in rows[3]["query_body"]

    def test_registration_survives_failed_runs(self, tmp_path):
        """Even a FAILED run records which catalogs produced the attempt."""
        broken = GaiaDR3IngestionPipeline(
            str(tmp_path / "gaia.db"), FakeTransport("ERROR: nope\n")
        )
        with pytest.raises(Exception):
            broken.ingest()
        conn = connect(str(tmp_path / "gaia.db"))
        row = get_source(conn, "GAIA_DR3")
        conn.close()
        assert row is not None
        assert row["reference_frame"] == "ICRS"
        assert row["reference_epoch"] == "J2016.0"


class TestRegistrySemantics:
    def test_reregistration_is_single_row(self, tmp_path):
        conn = connect(str(tmp_path / "r.db"))
        ensure_schema(conn)
        register_source(
            conn, dict(GAIA_DR3_SOURCE_METADATA), registered_utc="T1"
        )
        first = get_source(conn, "GAIA_DR3")
        assert first["first_registered_utc"] == "T1"
        register_source(
            conn, dict(GAIA_DR3_SOURCE_METADATA), registered_utc="T2"
        )
        second = get_source(conn, "GAIA_DR3")
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
        changed["catalog_name"] = "Gaia Data Release 3 (updated)"
        register_source(conn, changed)
        row = get_source(conn, "GAIA_DR3")
        conn.close()
        assert row["catalog_name"] == "Gaia Data Release 3 (updated)"

    def test_get_unknown_source_returns_none(self, tmp_path):
        conn = connect(str(tmp_path / "r.db"))
        ensure_schema(conn)
        assert get_source(conn, "tycho-2") is None
        conn.close()

    def test_missing_metadata_keys_rejected(self, tmp_path):
        conn = connect(str(tmp_path / "r.db"))
        ensure_schema(conn)
        with pytest.raises(IngestionError, match="missing required keys"):
            register_source(conn, {"source_key": "incomplete"})
        conn.close()

    def test_measurements_table_untouched_by_registration(self, tmp_path):
        conn = connect(str(tmp_path / "r.db"))
        ensure_schema(conn)
        register_all_archive_sources(conn)
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM stars_astrometry"
        ).fetchone()["n"]
        conn.close()
        assert count == 0

    def test_model_inferred_flagging_partitions_the_canonical_columns(self, tmp_path):
        """Every canonical column is catalog-REAL; gspphot carries the qualifier."""
        qualified = set(MODEL_INFERRED_COLUMNS)
        assert qualified <= set(COLUMN_NAMES)
        assert "source_id" not in qualified
        assert "ra" not in qualified and "dec" not in qualified
        assert "parallax" not in qualified
        _, _ = run_pipeline(tmp_path, one_valid_row())
        conn = connect(str(tmp_path / "gaia.db"))
        row = get_source(conn, "GAIA_DR3")
        conn.close()
        assert set(json.loads(row["model_inferred_columns"])) == qualified
