"""Gaia DR3 column catalog, provenance classification, and SQLite DDL.

PROVENANCE POLICY (binding)
    The row-level tag ``stars_astrometry.data_classification`` is
    ``DataProvenance.REAL_DATA``: it refers to the astrometric/photometric
    MEASUREMENTS and astrometric-solution statistics published in
    ``gaiadr3.gaia_source`` (ICRS, epoch J2016.0 as published).

    Five columns are NOT measurements: ``teff_gspphot``, ``logg_gspphot``,
    ``mh_gspphot``, ``distance_gspphot`` and ``ag_gspphot`` are GSP-Phot
    model-inferred astrophysical parameters (Apsis neural-network pipeline
    outputs). They are classified ``DataProvenance.DERIVED_DATA`` in the
    column catalog below and must never be presented as observations.
    Downstream consumers must consult :data:`DERIVED_COLUMNS` (single source
    of truth) rather than re-deriving the split.

NO DATA IS EMBEDDED HERE
    This module carries schema and classification metadata only. No Gaia
    records, catalog extracts, or datasets exist in this repository.
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
    GaiaColumn("teff_gspphot", DataProvenance.DERIVED_DATA,
                   "GSP-Phot effective temperature, K (model-inferred)"),
    GaiaColumn("logg_gspphot", DataProvenance.DERIVED_DATA,
                   "GSP-Phot surface gravity, dex (model-inferred)"),
    GaiaColumn("mh_gspphot", DataProvenance.DERIVED_DATA,
                   "GSP-Phot metallicity, dex (model-inferred)"),
    GaiaColumn("distance_gspphot", DataProvenance.DERIVED_DATA,
                   "GSP-Phot distance estimate, pc (model-inferred)"),
    GaiaColumn("ag_gspphot", DataProvenance.DERIVED_DATA,
                   "GSP-Phot extinction in G, mag (model-inferred)"),
)

#: All Gaia DR3 columns this pipeline ingests, in schema/insert order.
GAIA_DR3_COLUMNS: tuple[GaiaColumn, ...] = _COLUMNS

#: Column names in canonical order (single source for ADQL, CSV mapping, DDL).
COLUMN_NAMES: tuple[str, ...] = tuple(c.name for c in GAIA_DR3_COLUMNS)

#: GSP-Phot model-inferred columns -- DERIVED_DATA, never observations.
DERIVED_COLUMNS: tuple[str, ...] = tuple(
    c.name for c in GAIA_DR3_COLUMNS if c.provenance is DataProvenance.DERIVED_DATA
)

#: The row-level classification every ingested astrometry row carries.
ROW_DATA_CLASSIFICATION: DataProvenance = DataProvenance.REAL_DATA

# SQLite DDL. ``ra``/``dec`` are NOT NULL: validation refuses rows without
# coordinates, so the database enforces the same contract. Every other data
# column is nullable: an absent measurement is stored as SQL NULL, never 0.0
# and never a guessed substitute. ``source_id`` is the primary key, which is
# what makes re-ingestion conflict-detectable (see database.INSERT_SQL).
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

DDL_SOURCES_REGISTRY = """
CREATE TABLE IF NOT EXISTS sources_registry (
    source_name TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    endpoint_url TEXT NOT NULL,
    protocol TEXT NOT NULL,
    reference_frame TEXT NOT NULL,
    ref_epoch REAL NOT NULL,
    data_classification_default TEXT NOT NULL,
    derived_columns TEXT NOT NULL,
    first_registered_utc TEXT NOT NULL,
    updated_utc TEXT NOT NULL
)
"""

#: Catalog-source metadata for Gaia DR3, registered into ``sources_registry``
#: on every ingestion run (idempotently). This records HOW the data was
#: obtained and under which conventions: the ESA TAP endpoint, the IVOA
#: protocol, the ICRS reference frame and the J2016.0 reference epoch as
#: published (coordinates are stored exactly as Gaia publishes them; the
#: epoch belongs to catalog metadata, never fabricated into rows). The
#: classification default applies to measurements; the GSP-Phot columns are
#: flagged DERIVED_DATA via :data:`DERIVED_COLUMNS`.
GAIA_DR3_SOURCE_METADATA = {
    "source_name": "gaia_dr3",
    "title": "ESA Gaia DR3 (gaiadr3.gaia_source)",
    "endpoint_url": TAP_BASE_URL,
    "protocol": "IVOA TAP 1.1 / ADQL",
    "reference_frame": "ICRS",
    "ref_epoch": 2016.0,
    "data_classification_default": DataProvenance.REAL_DATA.value,
    "derived_columns": list(DERIVED_COLUMNS),
}
