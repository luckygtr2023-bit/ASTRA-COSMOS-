"""
ASTRA Backend — data access interfaces (§10, provenance, region management).

Provides explicit, validated access to:
  - Ingestion-backed catalog data (stars, exoplanets, solar system)
  - World regions / zones
  - Entity snapshots (read-only)

Contracts:
  - All returns carry provenance (REAL_DATA / DERIVED / SIMULATED ...)
  - Access pattern validation (no unbounded scans without pagination)
  - Never returns mutable authoritative handles
  - Graceful degradation when data sources unavailable (explicit error)
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from astra.celestial.provenance import DataProvenance

from astra.backend.exceptions import DataAccessError


class DataSource(str, Enum):
    ARCHIVE_STARS = "archive_stars"  # stars_astrometry
    ARCHIVE_EXOPLANETS = "archive_exoplanets"
    ARCHIVE_SOLAR_SYSTEM = "archive_solar_system"
    WORLD_REGIONS = "world_regions"
    ENTITIES = "entities"


@dataclass
class DataRequest:
    source: DataSource
    query: Dict[str, Any] = field(default_factory=dict)
    limit: int = 100
    offset: int = 0
    # provenance filter: if set, only rows with this provenance
    provenance: Optional[DataProvenance] = None
    # bounding region for spatial queries (ra/dec or world bounds)
    region: Optional[Dict[str, Any]] = None

    def validate(self) -> None:
        if not isinstance(self.source, DataSource):
            raise DataAccessError(f"source must be DataSource, got {self.source!r}", operation="validate", resource="request")
        if not isinstance(self.limit, int) or self.limit < 1 or self.limit > 10000:
            raise DataAccessError(f"limit must be in [1,10000], got {self.limit!r}", operation="validate", resource="limit")
        if not isinstance(self.offset, int) or self.offset < 0:
            raise DataAccessError(f"offset must be >=0, got {self.offset!r}", operation="validate", resource="offset")
        if self.provenance is not None and not isinstance(self.provenance, DataProvenance):
            raise DataAccessError(f"provenance must be DataProvenance, got {self.provenance!r}", operation="validate", resource="provenance")

    def cache_key(self) -> str:
        # deterministic, provenance-aware key
        parts = [
            self.source.value,
            str(self.limit),
            str(self.offset),
            (self.provenance.value if self.provenance else "*"),
        ]
        if self.query:
            parts.append(",".join(f"{k}={self.query[k]}" for k in sorted(self.query)))
        if self.region:
            parts.append(",".join(f"{k}={self.region[k]}" for k in sorted(self.region)))
        return "data:" + "|".join(parts)


@dataclass
class DataResponse:
    rows: List[Dict[str, Any]]
    total_hint: Optional[int] = None  # if known, else None
    provenance: DataProvenance = DataProvenance.DERIVED_DATA
    source: DataSource = DataSource.ARCHIVE_STARS
    truncated: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rows": [dict(r) for r in self.rows],
            "total_hint": self.total_hint,
            "provenance": self.provenance.value,
            "source": self.source.value,
            "truncated": self.truncated,
            "count": len(self.rows),
        }


class DataAccessService:
    """
    Explicit data access facade.

    Backed by callables that the integrator supplies (so we don't hard-wire
    a single ingestion DB path). If no callables supplied, data access is
    gracefully reported as unavailable rather than crashing.

    Each backend (archive, world) registers a handler for its DataSource.
    """

    def __init__(self):
        self._handlers: Dict[DataSource, Any] = {}
        self._lock = threading.Lock()
        self._query_count = 0
        self._error_count = 0

    def register_handler(self, source: DataSource, handler: Any) -> None:
        if not isinstance(source, DataSource):
            raise DataAccessError(f"source must be DataSource, got {source!r}", operation="register_handler", resource=str(source))
        if not callable(handler):
            raise DataAccessError("handler must be callable", operation="register_handler", resource=source.value)
        with self._lock:
            self._handlers[source] = handler

    def has_handler(self, source: DataSource) -> bool:
        with self._lock:
            return source in self._handlers

    def query(self, request: DataRequest) -> DataResponse:
        request.validate()
        with self._lock:
            handler = self._handlers.get(request.source)
            self._query_count += 1
        if handler is None:
            with self._lock:
                self._error_count += 1
            raise DataAccessError(
                f"no handler registered for source {request.source.value}",
                operation="query",
                resource=request.source.value,
                recoverable=False,
            )
        try:
            result = handler(request)
        except DataAccessError:
            with self._lock:
                self._error_count += 1
            raise
        except Exception as e:
            with self._lock:
                self._error_count += 1
            raise DataAccessError(f"handler failed for {request.source.value}: {e}", operation="query", resource=request.source.value, cause=e, recoverable=True)

        # Normalize result to DataResponse if handler returned list/dict
        if isinstance(result, DataResponse):
            return result
        if isinstance(result, list):
            # assume list of rows
            return DataResponse(rows=result, provenance=request.provenance or DataProvenance.REAL_DATA, source=request.source, truncated=len(result) >= request.limit)
        if isinstance(result, dict) and "rows" in result:
            rows = result.get("rows", [])
            return DataResponse(
                rows=rows,
                total_hint=result.get("total_hint"),
                provenance=DataProvenance(result.get("provenance", DataProvenance.DERIVED_DATA.value)) if isinstance(result.get("provenance"), str) else result.get("provenance", DataProvenance.DERIVED_DATA),
                source=request.source,
                truncated=result.get("truncated", False),
            )
        raise DataAccessError(f"handler returned unexpected type {type(result).__name__}", operation="query", resource=request.source.value)

    # convenience: direct archive query with SQL read-only if ingestion DB adapter supplied
    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "handlers": [s.value for s in self._handlers.keys()],
                "query_count": self._query_count,
                "error_count": self._error_count,
            }


# -- Ingestion DB passthrough helper (optional, no hard dependency) --

def make_archive_handler(db_path: str):
    """
    Factory for a simple sqlite read-only handler that exposes
    stars_astrometry / confirmed_exoplanets / solar_system_bodies.

    Only used if caller wants the canned passthrough; they may supply
    a custom handler instead. Provenance is REAL_DATA for these tables.
    """
    import sqlite3

    def handler(req: DataRequest) -> DataResponse:
        # Map source to table
        table_map = {
            DataSource.ARCHIVE_STARS: "stars_astrometry",
            DataSource.ARCHIVE_EXOPLANETS: "confirmed_exoplanets",
            DataSource.ARCHIVE_SOLAR_SYSTEM: "solar_system_bodies",
        }
        table = table_map.get(req.source)
        if table is None:
            raise DataAccessError(f"archive handler does not support {req.source.value}", operation="archive_query", resource=req.source.value)

        # Validate query keys to allow only safe filters (no SQL injection)
        allowed = {
            DataSource.ARCHIVE_STARS: {"source_id", "ra", "dec", "phot_g_mean_mag", "parallax"},
            DataSource.ARCHIVE_EXOPLANETS: {"pl_name", "hostname", "disc_year"},
            DataSource.ARCHIVE_SOLAR_SYSTEM: {"spkid", "name", "body_type"},
        }.get(req.source, set())

        filters = {}
        for k, v in (req.query or {}).items():
            if k not in allowed:
                raise DataAccessError(f"query key {k!r} not allowed for {req.source.value}", operation="archive_query", resource=k)
            filters[k] = v

        # Build safe parameterized query
        where_clauses = []
        params: List[Any] = []
        for k, v in filters.items():
            where_clauses.append(f"{k} = ?")
            params.append(v)
        # region support: for stars, optional ra/dec bounding box
        if req.region and req.source == DataSource.ARCHIVE_STARS:
            # expects {ra_min, ra_max, dec_min, dec_max}
            for key, col in [("ra_min", "ra"), ("ra_max", "ra"), ("dec_min", "dec"), ("dec_max", "dec")]:
                if key in req.region:
                    op = ">=" if "min" in key else "<="
                    where_clauses.append(f"{col} {op} ?")
                    params.append(float(req.region[key]))

        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        sql = f"SELECT * FROM {table}{where_sql} LIMIT ? OFFSET ?"
        params.extend([req.limit, req.offset])

        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5.0)
            conn.row_factory = sqlite3.Row
            cur = conn.execute(sql, params)
            rows = [dict(r) for r in cur.fetchall()]
            # add provenance annotation
            for r in rows:
                r.setdefault("data_classification", DataProvenance.REAL_DATA.value)
            conn.close()
        except Exception as e:
            raise DataAccessError(f"sqlite query failed: {e}", operation="archive_query", resource=table, cause=e, recoverable=True)

        return DataResponse(rows=rows, provenance=DataProvenance.REAL_DATA, source=req.source, truncated=len(rows) >= req.limit)

    return handler


__all__ = ["DataSource", "DataRequest", "DataResponse", "DataAccessService", "make_archive_handler"]
