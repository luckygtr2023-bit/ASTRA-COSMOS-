"""ASTRA catalog-ingestion exceptions.

Every exception derives from ``astra.core.exceptions.AstraError`` per the
ASTRA house convention (message + details dict). This layer defines the
ingestion failure taxonomy:

    MalformedRowError      one catalog row failed validation (rejected and
                           counted; never repaired by guessing).
    IngestionContractError a loud-failure condition: response header/schema
                           mismatch, TAP error payload, or a row-rejection
                           rate above the configured circuit breaker. Any
                           condition under which continuing would leave a
                           misleading database must raise this.
    IngestionRunError      run-lifecycle violation (unknown run, stale run).
    TransportError         network/HTTP failure talking to the TAP service
                           (OSError/URLError are wrapped so callers handle a
                           single exception family).
"""

from astra.core.exceptions import AstraError


class IngestionError(AstraError):
    """Base class for all catalog-ingestion errors."""


class MalformedRowError(IngestionError):
    """A catalog row failed field validation.

    The row is rejected and counted by the pipeline. It is NEVER silently
    repaired, coerced, or filled with a substitute value.
    """


class IngestionContractError(IngestionError):
    """Loud-failure contract violation.

    Raised for: unexpected response header (wrong/missing columns), TAP
    error payloads, and rejection-rate circuit-breaker trips. A run that
    hits this error is marked FAILED in the ingestion manifest.
    """


class IngestionRunError(IngestionError):
    """Ingestion run lifecycle violation (e.g. unknown run id)."""


class TransportError(IngestionError):
    """Network or HTTP failure while talking to a TAP endpoint."""
