"""Gaia DR3 column catalog, provenance classification, and SQLite DDL.

PROVENANCE POLICY (binding; per the ASTRA Celestial Objects master archive)
    The master archive ("ASTRA Celestial Objects System — Complete Master
    Architecture, Data Ingestion Specification, Database Dump & Python
    Pipeline Source Code", September 2026) defines the operational split:

        REAL_DATA     - values directly traceable to authoritative archives
                        (ESA Gaia DR3, NASA Exoplanet Archive, SIMBAD,
                        NASA/JPL Horizons). This INCLUDES the ESA-published
                        GSP-Phot astrophysical parameters: they are catalog
                        fields of gaiadr3.gaia_source, so every column of
                        ``stars_astrometry`` is REAL_DATA and the table
                        default is 'REAL_DATA' (archive section 2 DDL).
        DERIVED_DATA  - values computed BY ASTRA (spatial indexing,
                        cross-matching, epoch transformations) - i.e. the
                        ``astra_canonical_registry`` synthesis domain.

    Accordingly ALL 26 Gaia columns here are REAL_DATA. The five GSP-Phot
    columns carry an ADDITIONAL scientific qualifier,
    :data:`MODEL_INFERRED_COLUMNS` (Apsis neural-network outputs, not direct
    measurements) so downstream users keep the caveat without misstating
    the data's archive provenance. ``stars_astrometry.data_classification``
    is NOT NULL and always written explicitly (stricter than the archive's
    DEFAULT, which it otherwise matches column-for-column).

NO DATA IS EMBEDDED HERE
    This module carries schema and classification metadata only. The
    ``sources_registry`` rows and ``pipeline_queries`` rows are the master
    archive's normative CONFIGURATION (endpoints, protocols, frames,
    epochs, stored production queries) - not observational records. No
    Gaia/Exoplanet/SIMBAD/Horizons catalog data exists in this repository;
    the database stays empty until a real ingestion run populates it.
"""

from dataclasses import dataclass

from astra.celestial.provenance import DataProvenance
from astra.ingestion.transport import TAP_BASE_URL


@dataclass(frozen=True)
class GaiaColumn:
    """One ``gaiadr3.gaia_source`` column with its ASTRA provenance class."""

    name: str
    provenance: DataProvenance
    description: str = ""


_COLUMNS: tuple[GaiaColumn, ...] = (
    GaiaColumn("source_id", DataProvenance.REAL_DATA,
                   "Gaia DR3 source identifier (int64 primary key)"),
    GaiaColumn("designation", DataProvenance.REAL_DATA,
                   "IAS-name designation, e.g. 'Gaia DR3 <source_id>'"),
    GaiaColumn("ref_epoch", DataProvenance.REAL_DATA,
                   "reference epoch, Julian years (DR3: 2016.0, ICRS)"),
    GaiaColumn("ra", DataProvenance.REAL_DATA,
                   "right ascension, ICRS deg [0, 360]"),
    GaiaColumn("ra_error", DataProvenance.REAL_DATA,
                   "RA standard uncertainty, deg"),
    GaiaColumn("dec", DataProvenance.REAL_DATA,
                   "declination, ICRS deg [-90, 90]"),
    GaiaColumn("dec_error", DataProvenance.REAL_DATA,
                   "Dec standard uncertainty, deg"),
    GaiaColumn("parallax", DataProvenance.REAL_DATA,
                   "absolute parallax, mas"),
    GaiaColumn("parallax_error", DataProvenance.REAL_DATA,
                   "parallax standard uncertainty, mas"),
    GaiaColumn("pmra", DataProvenance.REAL_DATA,
                   "proper motion in RA (mu_alpha_cos_delta), mas/yr"),
    GaiaColumn("pmra_error", DataProvenance.REAL_DATA,
                   "proper-motion RA uncertainty, mas/yr"),
    GaiaColumn("pmdec", DataProvenance.REAL_DATA,
                   "proper motion in Dec, mas/yr"),
    GaiaColumn("pmdec_error", DataProvenance.REAL_DATA,
                   "proper-motion Dec uncertainty, mas/yr"),
    GaiaColumn("radial_velocity", DataProvenance.REAL_DATA,
                   "radial velocity, km/s (RVS sample only)"),
    GaiaColumn("radial_velocity_error", DataProvenance.REAL_DATA,
                   "radial-velocity uncertainty, km/s"),
    GaiaColumn("ruwe", DataProvenance.REAL_DATA,
                   "renormalised unit weight error (solution-fit statistic)"),
    GaiaColumn("astrometric_params_solved", DataProvenance.REAL_DATA,
                   "astrometric parameterisation code (5/31/55...)"),
    GaiaColumn("phot_g_mean_mag", DataProvenance.REAL_DATA,
                   "mean G-band magnitude"),
    GaiaColumn("phot_bp_mean_mag", DataProvenance.REAL_DATA,
                   "mean BP-band magnitude"),
    GaiaColumn("phot_rp_mean_mag", DataProvenance.REAL_DATA,
                   "mean RP-band magnitude"),
    GaiaColumn("bp_rp", DataProvenance.REAL_DATA,
                   "BP - RP observed colour"),
    GaiaColumn("teff_gspphot", DataProvenance.REAL_DATA,
                   "GSP-Phot effective temperature, K (ESA-published; "
                   "model-inferred qualifier)"),
    GaiaColumn("logg_gspphot", DataProvenance.REAL_DATA,
                   "GSP-Phot surface gravity, dex (ESA-published; "
                   "model-inferred qualifier)"),
    GaiaColumn("mh_gspphot", DataProvenance.REAL_DATA,
                   "GSP-Phot metallicity, dex (ESA-published; "
                   "model-inferred qualifier)"),
    GaiaColumn("distance_gspphot", DataProvenance.REAL_DATA,
                   "GSP-Phot distance estimate, pc (ESA-published; "
                   "model-inferred qualifier)"),
    GaiaColumn("ag_gspphot", DataProvenance.REAL_DATA,
                   "GSP-Phot extinction in G, mag (ESA-published; "
                   "model-inferred qualifier)"),
)

#: All Gaia DR3 columns this pipeline ingests, in schema/insert order.
GAIA_DR3_COLUMNS: tuple[GaiaColumn, ...] = _COLUMNS

#: Column names in canonical order (single source for ADQL, CSV mapping, DDL).
COLUMN_NAMES: tuple[str, ...] = tuple(c.name for c in GAIA_DR3_COLUMNS)

#: GSP-Phot columns: REAL_DATA catalog fields that are model-inferred
#: (Apsis pipeline outputs) rather than direct measurements. Scientific
#: qualifier only - the provenance class remains REAL_DATA per the master
#: archive, which reserves DERIVED_DATA for values computed BY ASTRA.
MODEL_INFERRED_COLUMNS: tuple[str, ...] = (
    "teff_gspphot",
    "logg_gspphot",
    "mh_gspphot",
    "distance_gspphot",
    "ag_gspphot",
)

#: ASTRA-computed (DERIVED_DATA) columns of ``stars_astrometry``: none.
#: Per the master archive, DERIVED_DATA applies to the ASTRA synthesis
#: domain (``astra_canonical_registry``: HEALPix indexing, cross-matching,
#: epoch transformation), not to any published Gaia column.
DERIVED_COLUMNS: tuple[str, ...] = ()

#: The row-level classification every ingested astrometry row carries.
ROW_DATA_CLASSIFICATION: DataProvenance = DataProvenance.REAL_DATA

# SQLite DDL. ``ra``/``dec`` are NOT NULL: validation refuses rows without
# coordinates, so the database enforces the same contract. Every other data
# column is nullable: an absent measurement is stored as SQL NULL, never 0.0
# and never a guessed substitute. ``source_id`` is the primary key, which is
# what makes re-ingestion conflict-detectable (see database.INSERT_SQL).
# Column set/order matches the master archive section 2 DDL exactly; the
# deviations are: IF NOT EXISTS (idempotent schema) and NOT NULL on
# data_classification (explicit over default).
DDL_STARS_ASTROMETRY = """
CREATE TABLE IF NOT EXISTS stars_astrometry (
    source_id TEXT PRIMARY KEY,
    designation TEXT,
    ref_epoch REAL,
    ra REAL NOT NULL,
    ra_error REAL,
    dec REAL NOT NULL,
    dec_error REAL,
    parallax REAL,
    parallax_error REAL,
    pmra REAL,
    pmra_error REAL,
    pmdec REAL,
    pmdec_error REAL,
    radial_velocity REAL,
    radial_velocity_error REAL,
    ruwe REAL,
    astrometric_params_solved INTEGER,
    phot_g_mean_mag REAL,
    phot_bp_mean_mag REAL,
    phot_rp_mean_mag REAL,
    bp_rp REAL,
    teff_gspphot REAL,
    logg_gspphot REAL,
    mh_gspphot REAL,
    distance_gspphot REAL,
    ag_gspphot REAL,
    data_classification TEXT NOT NULL
)
"""

#: Non-unique supporting indexes for spatial / distance-band queries.
DDL_INDEXES: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_gaia_ra_dec ON stars_astrometry (ra, dec)",
    "CREATE INDEX IF NOT EXISTS idx_gaia_parallax ON stars_astrometry (parallax)",
)

#: Run ledger (ASTRA pipeline addition beyond the archive's seven tables:
#: reproducibility metadata for ingestion runs; carries no catalog data).
DDL_MANIFEST = """
CREATE TABLE IF NOT EXISTS ingestion_manifest (
    run_id TEXT PRIMARY KEY,
    adql_hash TEXT NOT NULL,
    adql TEXT NOT NULL,
    params_json TEXT NOT NULL,
    status TEXT NOT NULL,
    failure TEXT,
    rows_inserted INTEGER NOT NULL DEFAULT 0,
    rows_skipped INTEGER NOT NULL DEFAULT 0,
    rows_rejected INTEGER NOT NULL DEFAULT 0,
    batches_committed INTEGER NOT NULL DEFAULT 0,
    started_utc TEXT NOT NULL,
    updated_utc TEXT NOT NULL
)
"""

# ---------------------------------------------------------------------------
# Master-archive normative tables (archive section 2, verbatim column sets)
# ---------------------------------------------------------------------------

#: Archive schema of ``sources_registry`` (section 2/3.1) extended with the
#: pipeline's additive annotation columns (classification default, the
#: model-inferred qualifier list, registration timestamps). The annotation
#: columns are nullable additions; the archive's own columns are NOT NULL
#: exactly as specified.
DDL_SOURCES_REGISTRY = """
CREATE TABLE IF NOT EXISTS sources_registry (
    source_key TEXT PRIMARY KEY,
    catalog_name TEXT NOT NULL,
    provider TEXT NOT NULL,
    release TEXT NOT NULL,
    endpoint_url TEXT NOT NULL,
    protocol TEXT NOT NULL,
    reference_frame TEXT NOT NULL,
    reference_epoch TEXT NOT NULL,
    data_classification_default TEXT,
    model_inferred_columns TEXT,
    first_registered_utc TEXT,
    updated_utc TEXT
)
"""

DDL_ASTRA_CANONICAL_REGISTRY = """
CREATE TABLE IF NOT EXISTS astra_canonical_registry (
    astra_uuid TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    object_class TEXT NOT NULL,
    gaia_source_id TEXT,
    simbad_oid INTEGER,
    jpl_spkid TEXT,
    exoplanet_name TEXT,
    healpix_index_order12 INTEGER,
    epoch_j2000_ra REAL,
    epoch_j2000_dec REAL,
    data_classification TEXT DEFAULT 'DERIVED_DATA'
)
"""

DDL_CONFIRMED_EXOPLANETS = """
CREATE TABLE IF NOT EXISTS confirmed_exoplanets (
    pl_name TEXT PRIMARY KEY,
    hostname TEXT NOT NULL,
    sy_snum INTEGER,
    sy_pnum INTEGER,
    discoverymethod TEXT,
    disc_facility TEXT,
    disc_year INTEGER,
    pl_orbper REAL,
    pl_orbpererr1 REAL,
    pl_orbpererr2 REAL,
    pl_orbsmax REAL,
    pl_orbsmaxerr1 REAL,
    pl_orbsmaxerr2 REAL,
    pl_rade REAL,
    pl_radeerr1 REAL,
    pl_radeerr2 REAL,
    pl_masse REAL,
    pl_masseerr1 REAL,
    pl_masseerr2 REAL,
    pl_bmassj REAL,
    st_teff REAL,
    st_rad REAL,
    st_mass REAL,
    ra REAL,
    dec REAL,
    default_flag INTEGER DEFAULT 1,
    data_classification TEXT DEFAULT 'REAL_DATA'
)
"""

DDL_OBJECT_ALIASES_CROSSIDS = """
CREATE TABLE IF NOT EXISTS object_aliases_crossids (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    main_id TEXT NOT NULL,
    catalog_alias TEXT NOT NULL,
    catalog_source TEXT NOT NULL,
    otype TEXT,
    data_classification TEXT DEFAULT 'REAL_DATA'
)
"""

DDL_PIPELINE_QUERIES = """
CREATE TABLE IF NOT EXISTS pipeline_queries (
    query_id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_catalog TEXT NOT NULL,
    query_type TEXT NOT NULL,
    endpoint_url TEXT NOT NULL,
    query_body TEXT NOT NULL
)
"""

DDL_SOLAR_SYSTEM_BODIES = """
CREATE TABLE IF NOT EXISTS solar_system_bodies (
    spkid TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    body_type TEXT NOT NULL,
    pdes TEXT,
    ref_plane TEXT DEFAULT 'ECLIPTIC',
    ref_system TEXT DEFAULT 'ICRF',
    eccentricity_ec REAL,
    perihelion_dist_qr REAL,
    inclination_in REAL,
    node_lon_om REAL,
    arg_peri_w REAL,
    semi_major_axis_a REAL,
    radius_km REAL,
    absolute_mag_h REAL,
    data_classification TEXT DEFAULT 'REAL_DATA'
)
"""

#: The master archive's seven core tables of ``astra_celestial_objects.db``.
ARCHIVE_TABLE_DDLS: tuple[str, ...] = (
    DDL_STARS_ASTROMETRY,
    DDL_SOURCES_REGISTRY,
    DDL_ASTRA_CANONICAL_REGISTRY,
    DDL_CONFIRMED_EXOPLANETS,
    DDL_OBJECT_ALIASES_CROSSIDS,
    DDL_PIPELINE_QUERIES,
    DDL_SOLAR_SYSTEM_BODIES,
)

# ---------------------------------------------------------------------------
# sources_registry metadata (archive section 3.1 dump - normative CONFIG,
# not observational data). Epochs are TEXT exactly as the archive publishes
# them ("J2016.0", "J2000.0", "Dynamic").
# ---------------------------------------------------------------------------

_GSPPHOT_QUALIFIER = list(MODEL_INFERRED_COLUMNS)

GAIA_DR3_SOURCE_METADATA = {
    "source_key": "GAIA_DR3",
    "catalog_name": "Gaia Data Release 3",
    "provider": "ESA ESAC",
    "release": "DR3",
    "endpoint_url": TAP_BASE_URL,
    "protocol": "IVOA TAP / ADQL",
    "reference_frame": "ICRS",
    "reference_epoch": "J2016.0",
    "data_classification_default": DataProvenance.REAL_DATA.value,
    "model_inferred_columns": _GSPPHOT_QUALIFIER,
}

NEXSCI_PS_SOURCE_METADATA = {
    "source_key": "NEXSCI_PS",
    "catalog_name": "Planetary Systems Table",
    "provider": "Caltech / NASA IPAC",
    "release": "Cumulative 2026",
    "endpoint_url": "https://exoplanetarchive.ipac.caltech.edu/TAP/sync",
    "protocol": "IVOA TAP / ADQL",
    "reference_frame": "ICRS",
    "reference_epoch": "J2000.0",
    "data_classification_default": DataProvenance.REAL_DATA.value,
    "model_inferred_columns": [],
}

SIMBAD_SOURCE_METADATA = {
    "source_key": "SIMBAD",
    "catalog_name": "SIMBAD Astronomical Database",
    "provider": "CDS Strasbourg",
    "release": "Release 1.8 (July 2026)",
    "endpoint_url": "https://simbad.u-strasbg.fr/simbad/sim-tap/sync",
    "protocol": "IVOA TAP / ADQL",
    "reference_frame": "ICRS",
    "reference_epoch": "J2000.0",
    "data_classification_default": DataProvenance.REAL_DATA.value,
    "model_inferred_columns": [],
}

JPL_HORIZONS_SOURCE_METADATA = {
    "source_key": "JPL_HORIZONS",
    "catalog_name": "JPL Solar System Dynamics Horizons",
    "provider": "NASA / JPL",
    "release": "DE440 / DE441",
    "endpoint_url": "https://ssd-api.jpl.nasa.gov/api/horizons.api",
    "protocol": "REST API",
    "reference_frame": "ICRF",
    "reference_epoch": "Dynamic",
    "data_classification_default": DataProvenance.REAL_DATA.value,
    "model_inferred_columns": [],
}

#: The four authoritative repositories of the master archive (section 3.1),
#: in archive order.
ARCHIVE_SOURCES_REGISTRY: tuple[dict, ...] = (
    GAIA_DR3_SOURCE_METADATA,
    NEXSCI_PS_SOURCE_METADATA,
    SIMBAD_SOURCE_METADATA,
    JPL_HORIZONS_SOURCE_METADATA,
)
