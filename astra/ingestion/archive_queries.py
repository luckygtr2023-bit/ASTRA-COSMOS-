"""Master-archive production query builders for the four authoritative catalogs.

Everything in this module is pure string/dict construction (archive section
3.7 "Stored Production API Queries" and section 4 reference pipeline). No
network access, no RNG, no side effects: identical arguments produce
byte-identical output. Execution goes through the transport/pipeline layers.

Catalogs (master archive section 3.1):
    GAIA_DR3      ESA ESAC TAP          ICRS J2016.0  (IVOA TAP / ADQL)
    NEXSCI_PS     Caltech / NASA IPAC   ICRS J2000.0  (IVOA TAP / ADQL)
    SIMBAD        CDS Strasbourg        ICRS J2000.0  (IVOA TAP / ADQL)
    JPL_HORIZONS  NASA / JPL            ICRF, dynamic epoch (REST API)

NOTE ON THE ARCHIVE'S TWO GAIA VARIANTS: the archive stores a TOP-50000
query without a RUWE gate (section 3.7, ``PIPELINE_QUERIES``) while its
reference builder applies ``parallax_over_error > 5 AND ruwe < 1.4``
(section 4, :func:`build_gaia_dr3_sample_query`). Both are implemented
exactly as specified; the stored row is configuration, the builder is the
quality-gated sampler.

NO CATALOG DATA LIVES HERE - query text and endpoints are configuration,
not observations.
"""

import urllib.parse

from astra.ingestion.transport import TAP_BASE_URL

#: Endpoint paths appended to TAP base URLs (archive section 3.7/4).
GAIA_SYNC_URL = TAP_BASE_URL + "/sync"
EXOPLANET_ARCHIVE_SYNC_URL = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"
SIMBAD_SYNC_URL = "https://simbad.u-strasbg.fr/simbad/sim-tap/sync"
JPL_HORIZONS_API_URL = "https://ssd-api.jpl.nasa.gov/api/horizons.api"
JPL_LOOKUP_API_URL = "https://ssd-api.jpl.nasa.gov/api/horizons_lookup.api"


def build_gaia_dr3_sample_query(limit: int = 1000) -> str:
    """Quality-gated Gaia DR3 sampler ADQL (archive section 4, verbatim spec).

    ``TOP {limit}``, high-precision astrometry/photometry columns, and the
    quality gates ``parallax_over_error > 5 AND ruwe < 1.4``.
    """
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError("limit must be a positive integer")
    return (
        f"SELECT TOP {limit} "
        "source_id, designation, ref_epoch, ra, ra_error, dec, dec_error, "
        "parallax, parallax_error, pmra, pmra_error, pmdec, pmdec_error, "
        "radial_velocity, radial_velocity_error, ruwe, astrometric_params_solved, "
        "phot_g_mean_mag, phot_bp_mean_mag, phot_rp_mean_mag, bp_rp "
        "FROM gaiadr3.gaia_source "
        "WHERE parallax IS NOT NULL AND parallax_over_error > 5 AND ruwe < 1.4;"
    )


def build_exoplanet_archive_query() -> str:
    """NASA Exoplanet Archive default-solution query (archive section 4)."""
    return (
        "select pl_name,hostname,sy_snum,sy_pnum,discoverymethod,disc_facility,"
        "disc_year,pl_orbper,pl_orbpererr1,pl_orbpererr2,pl_orbsmax,pl_orbsmaxerr1,"
        "pl_orbsmaxerr2,pl_rade,pl_radeerr1,pl_radeerr2,pl_masse,pl_masseerr1,"
        "pl_masseerr2,pl_bmassj,st_teff,st_rad,st_mass,ra,dec,default_flag "
        "from ps where default_flag=1"
    )


def build_simbad_aliases_query(limit: int = 500) -> str:
    """SIMBAD cross-identification alias query (archive section 4)."""
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError("limit must be a positive integer")
    return (
        f"SELECT DISTINCT TOP {limit} "
        "b.oid, b.main_id, b.otype, b.ra, b.dec, b.pmra, b.pmdec, "
        "b.plx_value, b.plx_err, i.id AS catalog_alias "
        "FROM basic AS b "
        "JOIN ident AS i ON b.oid = i.oidref "
        "WHERE b.ra IS NOT NULL AND b.dec IS NOT NULL;"
    )


def build_jpl_horizons_params(
    command: str = "499",
    start_time: str = "2026-01-01",
    stop_time: str = "2026-12-31",
) -> dict:
    """JPL Horizons REST parameters (archive section 4): ICRF state vectors.

    ``QUANTITIES='1,9,20'`` = state vectors + optional observer quantities;
    ``CENTER='500@0'`` = Sun-centered; ``EPHEM_TYPE='VECTORS'``.
    """
    if not command or not start_time or not stop_time:
        raise ValueError("command/start_time/stop_time must be non-empty")
    return {
        "format": "json",
        "COMMAND": f"'{command}'",
        "OBJ_DATA": "'YES'",
        "MAKE_EPHEM": "'YES'",
        "EPHEM_TYPE": "'VECTORS'",
        "CENTER": "'500@0'",
        "START_TIME": f"'{start_time}'",
        "STOP_TIME": f"'{stop_time}'",
        "STEP_SIZE": "'1d'",
        "QUANTITIES": "'1,9,20'",
    }


def build_jpl_horizons_url(
    command: str = "499",
    start_time: str = "2026-01-01",
    stop_time: str = "2026-12-31",
) -> str:
    """Full Horizons request URL (params urlencoded, archive section 4)."""
    query = urllib.parse.urlencode(build_jpl_horizons_params(command, start_time, stop_time))
    return f"{JPL_HORIZONS_API_URL}?{query}"


# ---------------------------------------------------------------------------
# pipeline_queries seed rows (archive section 3.7, stored verbatim)
# ---------------------------------------------------------------------------

_GAIA_STORED_QUERY = (
    "SELECT TOP 50000 source_id, ref_epoch, ra, ra_error, dec, dec_error, "
    "parallax, parallax_error, pmra, pmra_error, pmdec, pmdec_error, "
    "phot_g_mean_mag, phot_bp_mean_mag, phot_rp_mean_mag, "
    "radial_velocity, radial_velocity_error "
    "FROM gaiadr3.gaia_source "
    "WHERE parallax IS NOT NULL AND parallax_over_error > 5;"
)

_NEXSCI_STORED_QUERY = (
    "select pl_name,hostname,discoverymethod,pl_orbper,pl_orbpererr1,"
    "pl_orbpererr2,pl_orbsmax,pl_rade,pl_masse,ra,dec,default_flag "
    "from ps where default_flag=1"
)

_SIMBAD_STORED_QUERY = (
    "SELECT DISTINCT TOP 1000 b.oid, b.main_id, b.otype, b.ra, b.dec, b.pmra, "
    "b.pmdec, b.plx_value, b.plx_err, i.id AS alias "
    "FROM basic AS b JOIN ident AS i ON b.oid = i.oidref "
    "WHERE b.ra IS NOT NULL AND b.dec IS NOT NULL;"
)

_JPL_STORED_QUERY = (
    "COMMAND='499'&OBJ_DATA='YES'&MAKE_EPHEM='YES'&EPHEM_TYPE='VECTORS'&"
    "CENTER='500@0'&START_TIME='2026-01-01'&STOP_TIME='2026-12-31'&"
    "STEP_SIZE='1d'&QUANTITIES='1,9,20'"
)

#: The archive's four stored production queries (section 3.7), in order.
PIPELINE_QUERIES: tuple[dict, ...] = (
    {
        "target_catalog": "Gaia DR3",
        "query_type": "ADQL",
        "endpoint_url": GAIA_SYNC_URL,
        "query_body": _GAIA_STORED_QUERY,
    },
    {
        "target_catalog": "NASA Exoplanet Archive",
        "query_type": "HTTPS_TAP",
        "endpoint_url": EXOPLANET_ARCHIVE_SYNC_URL,
        "query_body": _NEXSCI_STORED_QUERY,
    },
    {
        "target_catalog": "SIMBAD",
        "query_type": "ADQL",
        "endpoint_url": SIMBAD_SYNC_URL,
        "query_body": _SIMBAD_STORED_QUERY,
    },
    {
        "target_catalog": "JPL Horizons",
        "query_type": "REST_API",
        "endpoint_url": JPL_HORIZONS_API_URL,
        "query_body": _JPL_STORED_QUERY,
    },
)
