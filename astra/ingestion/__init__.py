"""ASTRA Gaia DR3 catalog ingestion — real-data pipeline architecture.

This layer is the receptacle through which REAL astronomical catalog data
enters ASTRA. It contains NO data itself: no Gaia records, catalog
extracts, or datasets are embedded, downloaded, or fabricated anywhere in
this package (grep-verifiable). The pipeline preserves what the catalog
publishes:

    - unknown/absent values  -> SQL NULL (never 0.0, never a guess)
    - corrupt values         -> row rejected + counted (loud, not silent)
    - coordinates            -> ICRS pass-through, epoch as published
    - provenance             -> row-level REAL_DATA for measurements;
                                GSP-Phot columns flagged DERIVED_DATA
    - inserts                -> ON CONFLICT(source_id) DO NOTHING: an
                                authoritative row is never overwritten
    - every run              -> manifest ledger (ADQL + sha256, counters,
                                status, failure text)

DETERMINISM: identical CSV payload + identical query spec -> identical
database table content (manifest UTC stamps are metadata, not table data).

SCALE HONESTY: the sync path exists for probe queries (the Gaia archive
truncates long anonymous sync queries to 2,000 rows); batch-scale
ingestion (the ~2,000-ly quality-gated sample alone is order 10**7 rows)
uses the UWS async client; full-DR3-scale partitioned ingestion (e.g.
HEALPix chunks with per-chunk resume) is documented remaining work.
"""

from astra.ingestion.exceptions import (
    IngestionContractError,
    IngestionError,
    IngestionRunError,
    MalformedRowError,
    TransportError,
)
from astra.ingestion.schema import (
    COLUMN_NAMES,
    DERIVED_COLUMNS,
    GAIA_DR3_COLUMNS,
    GaiaColumn,
    ROW_DATA_CLASSIFICATION,
)
from astra.ingestion.query import (
    DEFAULT_MAX_RUWE,
    DEFAULT_PARALLAX_OVER_ERROR,
    LY_PER_PARSEC,
    MIN_PARALLAX_MAS_2000LY,
    SELECTION_RADIUS_LY,
    SELECTION_RADIUS_PC,
    GaiaQuerySpec,
    build_adql,
    query_hash,
)
from astra.ingestion.validate import GaiaRecord, validate_row
from astra.ingestion.database import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_RUNNING,
    INSERT_SQL,
    IngestionManifest,
    connect,
    ensure_schema,
    insert_batch,
)
from astra.ingestion.transport import (
    TAP_BASE_URL,
    TapTransport,
    UrllibTapTransport,
    UwsAsyncClient,
)
from astra.ingestion.pipeline import (
    GaiaDR3IngestionPipeline,
    IngestionRunResult,
)

__all__ = [
    # exceptions
    "IngestionError", "MalformedRowError", "IngestionContractError",
    "IngestionRunError", "TransportError",
    # schema
    "GaiaColumn", "GAIA_DR3_COLUMNS", "COLUMN_NAMES", "DERIVED_COLUMNS",
    "ROW_DATA_CLASSIFICATION",
    # query
    "GaiaQuerySpec", "build_adql", "query_hash", "MIN_PARALLAX_MAS_2000LY",
    "SELECTION_RADIUS_LY", "SELECTION_RADIUS_PC", "LY_PER_PARSEC",
    "DEFAULT_PARALLAX_OVER_ERROR", "DEFAULT_MAX_RUWE",
    # validation
    "GaiaRecord", "validate_row",
    # database
    "connect", "ensure_schema", "insert_batch", "IngestionManifest", "INSERT_SQL",
    "STATUS_RUNNING", "STATUS_COMPLETED", "STATUS_FAILED",
    # transport
    "TAP_BASE_URL", "TapTransport", "UrllibTapTransport", "UwsAsyncClient",
    # pipeline
    "GaiaDR3IngestionPipeline", "IngestionRunResult",
]
