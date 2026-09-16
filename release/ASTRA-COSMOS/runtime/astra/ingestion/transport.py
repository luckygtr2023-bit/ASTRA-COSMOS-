"""TAP transport: stdlib-only HTTP (urllib) with a pluggable seam for tests.

Two access modes against an IVOA TAP service (default: ESA Gaia archive,
``TAP_BASE_URL``):

    SYNC   POST {base}/sync  -- streaming CSV response. Limited (see
           query.py): probe queries only; a long-running anonymous sync
           query is truncated to 2,000 rows by the server.
    ASYNC  UWS: POST {base}/async creates a job; POST {job}/phase PHASE=RUN
           starts it; GET {job}/phase polls (QUEUED/EXECUTING/COMPLETED/
           ERROR/ABORTED); GET {job}/results/result streams the CSV.
           This is the batch-scale path (90 min / 3M-row anonymous caps).

NO NETWORK IN TESTS: the test suite injects fake transports; the default
:class:`UrllibTapTransport` is the production implementation and wraps all
OSError/URLError/HTTPError failures into :class:`TransportError` so callers
handle one exception family.
"""

import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Iterator, Mapping, Protocol

from astra.ingestion.exceptions import TransportError

#: ESA Gaia DR3 TAP service base URL (sync = {base}/sync, async = {base}/async).
TAP_BASE_URL = "https://gea.esac.esa.int/tap-server/tap"

_HTTP_TIMEOUT_S = 60.0
_UWS_TERMINAL_BAD = ("ERROR", "ABORTED")


class TapTransport(Protocol):
    """The single seam between the pipeline and the network."""

    def post_sync(self, base_url: str, payload: Mapping[str, str]) -> Iterator[bytes]:
        """POST a synchronous TAP query; return an iterator of raw lines."""
        ...

    def uws_create_job(self, base_url: str, adql: str) -> str:
        """Create an async UWS job; return the job URL."""
        ...

    def uws_set_phase(self, job_url: str, phase: str) -> None:
        """Set the UWS job phase (e.g. RUN)."""
        ...

    def uws_get_phase(self, job_url: str) -> str:
        """Return the current UWS job phase string."""
        ...

    def stream_url(self, url: str) -> Iterator[bytes]:
        """GET a URL; return an iterator of raw lines."""
        ...


def _wrap(exc: Exception, what: str, url: str) -> TransportError:
    return TransportError(
        f"{what} failed",
        {"url": url, "error": f"{type(exc).__name__}: {exc}"},
    )


class UrllibTapTransport:
    """Production transport over :mod:`urllib` (no third-party dependency)."""

    def _open(self, request: urllib.request.Request) -> Iterator[bytes]:
        try:
            response = urllib.request.urlopen(request, timeout=_HTTP_TIMEOUT_S)
        except urllib.error.HTTPError as exc:  # noqa: PERF203 - distinct wrap
            raise _wrap(exc, "HTTP error", request.full_url) from exc
        except (OSError, urllib.error.URLError) as exc:
            raise _wrap(exc, "network request", request.full_url) from exc
        return iter(response)

    def post_sync(self, base_url: str, payload: Mapping[str, str]) -> Iterator[bytes]:
        url = base_url.rstrip("/") + "/sync"
        data = urllib.parse.urlencode(dict(payload)).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        return self._open(request)

    def uws_create_job(self, base_url: str, adql: str) -> str:
        url = base_url.rstrip("/") + "/async"
        payload = {
            "REQUEST": "doQuery",
            "LANG": "ADQL",
            "FORMAT": "csv",
            "QUERY": adql,
        }
        data = urllib.parse.urlencode(payload).encode("utf-8")
        request = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            response = urllib.request.urlopen(request, timeout=_HTTP_TIMEOUT_S)
        except urllib.error.HTTPError as exc:
            # UWS creation answers 303 See Other with the job URL in Location.
            location = exc.headers.get("Location") if exc.headers else None
            if location:
                return location
            raise _wrap(exc, "UWS job creation", url) from exc
        except (OSError, urllib.error.URLError) as exc:
            raise _wrap(exc, "UWS job creation", url) from exc
        location = response.headers.get("Location")
        if location:
            return location
        return url + "/" + response.read().decode("utf-8", "replace").strip()

    def uws_set_phase(self, job_url: str, phase: str) -> None:
        url = job_url.rstrip("/") + "/phase"
        data = urllib.parse.urlencode({"PHASE": phase}).encode("utf-8")
        request = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            urllib.request.urlopen(request, timeout=_HTTP_TIMEOUT_S)
        except urllib.error.HTTPError as exc:
            # 303 redirect on phase change is normal UWS behaviour.
            if exc.code not in (302, 303):
                raise _wrap(exc, "UWS phase update", url) from exc
        except (OSError, urllib.error.URLError) as exc:
            raise _wrap(exc, "UWS phase update", url) from exc

    def uws_get_phase(self, job_url: str) -> str:
        request = urllib.request.Request(job_url.rstrip("/") + "/phase", method="GET")
        try:
            response = urllib.request.urlopen(request, timeout=_HTTP_TIMEOUT_S)
            return response.read().decode("utf-8", "replace").strip()
        except urllib.error.HTTPError as exc:
            raise _wrap(exc, "UWS phase poll", job_url) from exc
        except (OSError, urllib.error.URLError) as exc:
            raise _wrap(exc, "UWS phase poll", job_url) from exc

    def stream_url(self, url: str) -> Iterator[bytes]:
        return self._open(urllib.request.Request(url, method="GET"))


class UwsAsyncClient:
    """Run one ADQL query as an async UWS job; stream the CSV result.

    Polling sleeps ``poll_interval_s`` between phase checks and raises
    ``TransportError`` if the job ends in ERROR/ABORTED or exceeds
    ``max_wait_s``. Batch-scale ingestion uses this client; the sync path
    is for probe queries only (server-side truncation limits).
    """

    def __init__(
        self,
        transport: TapTransport,
        base_url: str = TAP_BASE_URL,
        poll_interval_s: float = 5.0,
        max_wait_s: float = 90.0 * 60.0,
    ):
        self._transport = transport
        self._base_url = base_url
        self._poll_interval_s = poll_interval_s
        self._max_wait_s = max_wait_s

    def stream_adql(self, adql: str) -> Iterator[bytes]:
        job_url = self._transport.uws_create_job(self._base_url, adql)
        self._transport.uws_set_phase(job_url, "RUN")
        waited = 0.0
        while True:
            phase = self._transport.uws_get_phase(job_url).upper()
            if phase == "COMPLETED":
                return self._transport.stream_url(
                    job_url.rstrip("/") + "/results/result"
                )
            if phase in _UWS_TERMINAL_BAD:
                raise TransportError(
                    f"UWS job ended in {phase}",
                    {"job_url": job_url, "phase": phase},
                )
            if waited >= self._max_wait_s:
                raise TransportError(
                    "UWS job exceeded max wait",
                    {"job_url": job_url, "waited_s": waited},
                )
            time.sleep(self._poll_interval_s)
            waited += self._poll_interval_s
