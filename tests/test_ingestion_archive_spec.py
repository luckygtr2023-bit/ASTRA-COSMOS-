"""Master-archive conformance tests.

Verifies the implementation against the ASTRA Celestial Objects master
archive ("Complete Master Architecture, Data Ingestion Specification,
Database Dump & Python Pipeline Source Code", September 2026, branch
``astra-cosmos-world-system-design-1ffcb``):

    section 2  - seven normative table DDLs of astra_celestial_objects.db
    section 3.1 - sources_registry four-catalog metadata dump
    section 3.7 - four stored production queries (pipeline_queries)
    section 4  - reference query builders for the four catalogs
    section 1  - provenance split (REAL_DATA = archive-traceable,
                 DERIVED_DATA = ASTRA-computed)

The ONE record-shaped fixture below (a Barnard's Star row quoting the
archive's own section 3.2 values) exists to exercise validation/storage
paths against spec-quoted numbers. It lives ONLY in this test file: the
production database remains empty until a real ingestion run, and nothing
catalog-shaped is embedded in astra/ (grep-verified by
TestRepositoryHygiene).
"""

import json
import urllib.parse

import pytest

from astra.ingestion import (
    ARCHIVE_SOURCES_REGISTRY,
    COLUMN_NAMES,
    DERIVED_COLUMNS,
    EXOPLANET_ARCHIVE_SYNC_URL,
    GAIA_SYNC_URL,
    JPL_HORIZONS_API_URL,
    MODEL_INFERRED_COLUMNS,
    PIPELINE_QUERIES,
    SIMBAD_SYNC_URL,
    build_exoplanet_archive_query,
    build_gaia_dr3_sample_query,
    build_jpl_horizons_params,
    build_jpl_horizons_url,
    build_simbad_aliases_query,
    connect,
    ensure_schema,
    get_source,
    validate_row,
)
from astra.celestial.provenance import DataProvenance
from test_ingestion_pipeline import csv_bytes, make_row, run_pipeline


ARCHIVE_TABLES = {
    "stars_astrometry": [
        "source_id", "designation", "ref_epoch", "ra", "ra_error", "dec",
        "dec_error", "parallax", "parallax_error", "pmra", "pmra_error",
        "pmdec", "pmdec_error", "radial_velocity", "radial_velocity_error",
        "ruwe", "astrometric_params_solved", "phot_g_mean_mag",
        "phot_bp_mean_mag", "phot_rp_mean_mag", "bp_rp", "teff_gspphot",
        "logg_gspphot", "mh_gspphot", "distance_gspphot", "ag_gspphot",
        "data_classification",
    ],
    "astra_canonical_registry": [
        "astra_uuid", "canonical_name", "object_class", "gaia_source_id",
        "simbad_oid", "jpl_spkid", "exoplanet_name",
        "healpix_index_order12", "epoch_j2000_ra", "epoch_j2000_dec",
        "data_classification",
    ],
    "confirmed_exoplanets": [
        "pl_name", "hostname", "sy_snum", "sy_pnum", "discoverymethod",
        "disc_facility", "disc_year", "pl_orbper", "pl_orbpererr1",
        "pl_orbpererr2", "pl_orbsmax", "pl_orbsmaxerr1", "pl_orbsmaxerr2",
        "pl_rade", "pl_radeerr1", "pl_radeerr2", "pl_masse", "pl_masseerr1",
        "pl_masseerr2", "pl_bmassj", "st_teff", "st_rad", "st_mass", "ra",
        "dec", "default_flag", "data_classification",
    ],
    "object_aliases_crossids": [
        "id", "main_id", "catalog_alias", "catalog_source", "otype",
        "data_classification",
    ],
    "pipeline_queries": [
        "query_id", "target_catalog", "query_type", "endpoint_url",
        "query_body",
    ],
    "solar_system_bodies": [
        "spkid", "name", "body_type", "pdes", "ref_plane", "ref_system",
        "eccentricity_ec", "perihelion_dist_qr", "inclination_in",
        "node_lon_om", "arg_peri_w", "semi_major_axis_a", "radius_km",
        "absolute_mag_h", "data_classification",
    ],
    "sources_registry": [
        "source_key", "catalog_name", "provider", "release", "endpoint_url",
        "protocol", "reference_frame", "reference_epoch",
        "data_classification_default", "model_inferred_columns",
        "first_registered_utc", "updated_utc",
    ],
}


@pytest.fixture()
def archive_db(tmp_path):
    db = str(tmp_path / "archive.db")
    conn = connect(db)
    ensure_schema(conn)
    yield conn
    conn.close()


class TestArchiveSection2DDL:
    @pytest.mark.parametrize(
        "table", list(ARCHIVE_TABLES), ids=list(ARCHIVE_TABLES)
    )
    def test_column_sets_match_archive_ddl_exactly(self, archive_db, table):
        info = archive_db.execute(f"PRAGMA table_info({table})").fetchall()
        assert [r["name"] for r in info] == ARCHIVE_TABLES[table]

    def test_primary_keys(self, archive_db):
        expected = {
            "stars_astrometry": "source_id",
            "astra_canonical_registry": "astra_uuid",
            "confirmed_exoplanets": "pl_name",
            "solar_system_bodies": "spkid",
            "sources_registry": "source_key",
        }
        for table, pk in expected.items():
            info = archive_db.execute(
                f"PRAGMA table_info({table})"
            ).fetchall()
            pk_cols = [r["name"] for r in info if r["pk"]]
            assert pk_cols == [pk], table

    def test_aliases_and_queries_autoincrement(self, archive_db):
        for table in ("object_aliases_crossids", "pipeline_queries"):
            info = archive_db.execute(
                f"PRAGMA table_info({table})"
            ).fetchall()
            assert any(r["name"] == "id" or r["name"] == "query_id" for r in info)

    def test_solar_system_ref_defaults(self, archive_db):
        archive_db.execute(
            "INSERT INTO solar_system_bodies (spkid, name, body_type) "
            "VALUES ('test-1', 'Test Body', 'asteroid')"
        )
        row = archive_db.execute(
            "SELECT ref_plane, ref_system, data_classification "
            "FROM solar_system_bodies WHERE spkid = 'test-1'"
        ).fetchone()
        archive_db.rollback()
        assert row["ref_plane"] == "ECLIPTIC"
        assert row["ref_system"] == "ICRF"
        assert row["data_classification"] == "REAL_DATA"

    def test_canonical_registry_default_is_derived(self, archive_db):
        archive_db.execute(
            "INSERT INTO astra_canonical_registry (astra_uuid, canonical_name, "
            "object_class) VALUES ('u-1', 'Test', 'Star')"
        )
        row = archive_db.execute(
            "SELECT data_classification FROM astra_canonical_registry "
            "WHERE astra_uuid = 'u-1'"
        ).fetchone()
        archive_db.rollback()
        assert row["data_classification"] == "DERIVED_DATA"

    def test_archive_tables_start_empty(self, archive_db):
        """Schema conformance ships NO catalog data."""
        for table in ARCHIVE_TABLES:
            count = archive_db.execute(
                f"SELECT COUNT(*) AS n FROM {table}"
            ).fetchone()["n"]
            assert count == 0, table


class TestArchiveSection31SourcesRegistry:
    def test_four_catalogs_with_archive_values(self, archive_db):
        from astra.ingestion import register_all_archive_sources

        register_all_archive_sources(archive_db)
        rows = {
            r["source_key"]: r
            for r in archive_db.execute("SELECT * FROM sources_registry")
        }
        assert set(rows) == {"GAIA_DR3", "NEXSCI_PS", "SIMBAD", "JPL_HORIZONS"}

        assert rows["GAIA_DR3"]["catalog_name"] == "Gaia Data Release 3"
        assert rows["GAIA_DR3"]["provider"] == "ESA ESAC"
        assert rows["GAIA_DR3"]["release"] == "DR3"
        assert rows["GAIA_DR3"]["protocol"] == "IVOA TAP / ADQL"
        assert rows["GAIA_DR3"]["reference_frame"] == "ICRS"
        assert rows["GAIA_DR3"]["reference_epoch"] == "J2016.0"

        assert rows["NEXSCI_PS"]["catalog_name"] == "Planetary Systems Table"
        assert rows["NEXSCI_PS"]["reference_epoch"] == "J2000.0"
        assert rows["NEXSCI_PS"]["endpoint_url"] == EXOPLANET_ARCHIVE_SYNC_URL

        assert rows["SIMBAD"]["provider"] == "CDS Strasbourg"
        assert rows["SIMBAD"]["endpoint_url"] == SIMBAD_SYNC_URL

        assert rows["JPL_HORIZONS"]["release"] == "DE440 / DE441"
        assert rows["JPL_HORIZONS"]["protocol"] == "REST API"
        assert rows["JPL_HORIZONS"]["reference_frame"] == "ICRF"
        assert rows["JPL_HORIZONS"]["reference_epoch"] == "Dynamic"

    def test_constant_order_matches_archive(self):
        assert [s["source_key"] for s in ARCHIVE_SOURCES_REGISTRY] == [
            "GAIA_DR3",
            "NEXSCI_PS",
            "SIMBAD",
            "JPL_HORIZONS",
        ]

    def test_gaia_endpoint_matches_transport_constant(self):
        gaia = next(
            s for s in ARCHIVE_SOURCES_REGISTRY if s["source_key"] == "GAIA_DR3"
        )
        assert gaia["endpoint_url"] == GAIA_SYNC_URL.removesuffix("/sync")
        assert gaia["endpoint_url"] == "https://gea.esac.esa.int/tap-server/tap"


class TestArchiveSection37StoredQueries:
    def test_four_rows_in_archive_order(self):
        assert [(q["target_catalog"], q["query_type"]) for q in PIPELINE_QUERIES] == [
            ("Gaia DR3", "ADQL"),
            ("NASA Exoplanet Archive", "HTTPS_TAP"),
            ("SIMBAD", "ADQL"),
            ("JPL Horizons", "REST_API"),
        ]

    def test_gaia_stored_query_spec(self):
        body = PIPELINE_QUERIES[0]["query_body"]
        assert "TOP 50000" in body
        assert "FROM gaiadr3.gaia_source" in body
        assert "parallax IS NOT NULL AND parallax_over_error > 5" in body
        assert PIPELINE_QUERIES[0]["endpoint_url"] == GAIA_SYNC_URL

    def test_exoplanet_stored_query_spec(self):
        body = PIPELINE_QUERIES[1]["query_body"]
        assert "from ps where default_flag=1" in body
        assert PIPELINE_QUERIES[1]["endpoint_url"] == EXOPLANET_ARCHIVE_SYNC_URL

    def test_simbad_stored_query_spec(self):
        body = PIPELINE_QUERIES[2]["query_body"]
        assert "TOP 1000" in body
        assert "JOIN ident AS i ON b.oid = i.oidref" in body
        assert "AS alias" in body
        assert PIPELINE_QUERIES[2]["endpoint_url"] == SIMBAD_SYNC_URL

    def test_jpl_stored_query_spec(self):
        body = PIPELINE_QUERIES[3]["query_body"]
        assert "COMMAND='499'" in body
        assert "EPHEM_TYPE='VECTORS'" in body
        assert "CENTER='500@0'" in body
        assert "QUANTITIES='1,9,20'" in body
        assert PIPELINE_QUERIES[3]["endpoint_url"] == JPL_HORIZONS_API_URL

    def test_seed_is_idempotent(self, archive_db):
        from astra.ingestion import seed_pipeline_queries

        assert seed_pipeline_queries(archive_db) == 4
        assert seed_pipeline_queries(archive_db) == 0
        count = archive_db.execute(
            "SELECT COUNT(*) AS n FROM pipeline_queries"
        ).fetchone()["n"]
        assert count == 4


class TestArchiveSection4Builders:
    def test_gaia_builder_quality_gated(self):
        query = build_gaia_dr3_sample_query()
        assert "TOP 1000" in query
        assert "parallax_over_error > 5 AND ruwe < 1.4" in query
        assert "astrometric_params_solved" in query
        assert "bp_rp" in query

    def test_gaia_builder_limit(self):
        assert "TOP 7" in build_gaia_dr3_sample_query(limit=7)

    def test_gaia_builder_rejects_bad_limit(self):
        for bad in (0, -1, 2.5, True, "10"):
            with pytest.raises(ValueError):
                build_gaia_dr3_sample_query(limit=bad)

    def test_exoplanet_builder_matches_archive(self):
        query = build_exoplanet_archive_query()
        assert query.startswith("select pl_name,hostname,sy_snum,sy_pnum")
        assert "pl_masseerr2" in query
        assert "st_mass,ra,dec,default_flag from ps where default_flag=1" in query

    def test_simbad_builder(self):
        query = build_simbad_aliases_query(limit=250)
        assert "TOP 250" in query
        assert "b.plx_value, b.plx_err" in query
        assert "i.id AS catalog_alias" in query

    def test_jpl_params_and_url(self):
        params = build_jpl_horizons_params()
        assert params["COMMAND"] == "'499'"
        assert params["STEP_SIZE"] == "'1d'"
        url = build_jpl_horizons_url()
        assert url.startswith(JPL_HORIZONS_API_URL + "?")
        assert "COMMAND=%27499%27" in url
        assert urllib.parse.unquote(url).count("COMMAND='499'") == 1

    def test_builders_deterministic_100x(self):
        for _ in range(100):
            assert build_gaia_dr3_sample_query() == build_gaia_dr3_sample_query()
            assert build_exoplanet_archive_query() == build_exoplanet_archive_query()
            assert build_simbad_aliases_query() == build_simbad_aliases_query()
            assert build_jpl_horizons_url() == build_jpl_horizons_url()


class TestArchiveSection1Provenance:
    def test_every_gaia_column_is_real_data(self):
        from astra.ingestion import GAIA_DR3_COLUMNS

        assert all(
            c.provenance is DataProvenance.REAL_DATA for c in GAIA_DR3_COLUMNS
        )

    def test_derived_vs_model_inferred_split(self):
        # DERIVED_DATA = ASTRA-computed (canonical registry domain):
        assert DERIVED_COLUMNS == ()
        # GSP-Phot: REAL_DATA catalog fields, model-inferred qualifier:
        assert set(MODEL_INFERRED_COLUMNS) == {
            "teff_gspphot", "logg_gspphot", "mh_gspphot",
            "distance_gspphot", "ag_gspphot",
        }

    def test_row_classification_written_real_data(self, tmp_path):
        row = make_row(7101)
        _, result = run_pipeline(tmp_path, csv_bytes([row]))
        assert result.rows_inserted == 1
        conn = connect(str(tmp_path / "gaia.db"))
        stored = conn.execute(
            "SELECT data_classification FROM stars_astrometry"
        ).fetchone()
        conn.close()
        assert stored["data_classification"] == "REAL_DATA"


class TestArchiveSection32FixtureValidation:
    """A Barnard's Star row quoting the archive's section 3.2 values.

    Purpose: prove the pipeline ACCEPTS the spec's own published record
    shape. These numbers exist only in this test file as a labeled
    spec-conformance fixture - never as production data.
    """

    BARNARD = {
        "source_id": "4472832130942575872",
        "designation": "Gaia DR3 4472832130942575872",
        "ref_epoch": "2016.0",
        "ra": "269.452",       # archive section 3.2 (deg, ICRS J2016.0)
        "dec": "4.693",
        "parallax": "547.45",  # mas
        "pmra": "-798.5",      # mas/yr
        "pmdec": "10327.8",
        "ruwe": "1.02",
        "phot_g_mean_mag": "9.51",
        "teff_gspphot": "3134.0",
    }

    def test_archive_quoted_record_passes_and_stores(self, tmp_path):
        row = make_row(7200, **self.BARNARD)  # source_id overridden by fixture
        _, result = run_pipeline(tmp_path, csv_bytes([row]))
        assert result.status == "COMPLETED"
        assert result.rows_inserted == 1
        conn = connect(str(tmp_path / "gaia.db"))
        stored = conn.execute(
            "SELECT ra, dec, parallax, pmra, pmdec, ruwe, phot_g_mean_mag, "
            "teff_gspphot FROM stars_astrometry WHERE source_id = ?",
            (self.BARNARD["source_id"],),
        ).fetchone()
        conn.close()
        assert stored is not None
        assert stored["ra"] == pytest.approx(269.452)
        assert stored["dec"] == pytest.approx(4.693)
        assert stored["parallax"] == pytest.approx(547.45)
        assert stored["pmra"] == pytest.approx(-798.5)
        assert stored["pmdec"] == pytest.approx(10327.8)
        assert stored["ruwe"] == pytest.approx(1.02)
        assert stored["phot_g_mean_mag"] == pytest.approx(9.51)
        assert stored["teff_gspphot"] == pytest.approx(3134.0)

    def test_programmatic_record_from_quoted_values(self):
        record = validate_row(make_row(7201, **self.BARNARD))
        assert record.source_id == self.BARNARD["source_id"]
        assert record.ref_epoch == 2016.0
        assert record.data_classification is DataProvenance.REAL_DATA
