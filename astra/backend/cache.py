"""
ASTRA Backend — bounded, explicit cache infrastructure.

Contracts (§16):
  - Bounded (max entries + max memory): LRU eviction, deterministic.
  - Explicit invalidation: by key, prefix, tag, or provenance.
  - TTL-aware (monotonic clock), lazy expiry on access.
  - Thread-safe (lock guarded).
  - Provenance preservation: cached values carry provenance + tick;
    stale authoritative state never returned as authoritative.
  - No hidden refresh: callers must pass fresh compute fn; cache never
    mutates simulation state.
"""

from __future__ import annotations

import time
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from astra.backend.exceptions import CacheError


@dataclass
class CacheEntry:
    value: Any
    provenance: str = "derived"  # e.g. REAL_DATA / DERIVED_DATA / SIMULATED_DATA / cache
    source_tick: int = -1  # simulation tick when sourced
    created_monotonic: float = 0.0
    ttl_s: float = 30.0
    tags: Set[str] = field(default_factory=set)
    size_bytes: int = 0  # approx; caller may supply

    def is_expired(self, now: float) -> bool:
        if self.ttl_s <= 0:
            return True  # 0 TTL means never cache / immediately expired
        if self.ttl_s >= 86400 * 365:  # effectively infinite if set huge, but spec says max 86400
            return False
        return (now - self.created_monotonic) > self.ttl_s

    def clone_value(self) -> Any:
        # shallow best-effort isolation; values that are dicts/lists we copy
        if isinstance(self.value, dict):
            return dict(self.value)
        if isinstance(self.value, list):
            return list(self.value)
        return self.value


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expiries: int = 0
    invalidations: int = 0
    entries: int = 0
    estimated_memory_bytes: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "expiries": self.expiries,
            "invalidations": self.invalidations,
            "entries": self.entries,
            "estimated_memory_bytes": self.estimated_memory_bytes,
            "hit_rate": self.hits / max(1, self.hits + self.misses),
        }


class BoundedCache:
    """
    Bounded LRU cache with explicit invalidation and TTL.

    Not a global singleton — caller owns lifecycle; runtime/services
    create scoped instances. Thread-safe.
    """

    def __init__(
        self,
        max_entries: int = 2048,
        max_memory_bytes: int = 256 * 1024 * 1024,
        default_ttl_s: float = 30.0,
        name: str = "astra.cache",
    ):
        if not isinstance(max_entries, int) or max_entries < 1:
            raise CacheError(f"max_entries must be >=1, got {max_entries!r}", operation="init", resource=name)
        if not isinstance(max_memory_bytes, int) or max_memory_bytes < 1024:
            raise CacheError(f"max_memory_bytes must be >=1024, got {max_memory_bytes!r}", operation="init", resource=name)
        self._max_entries = max_entries
        self._max_memory = max_memory_bytes
        self._default_ttl = float(default_ttl_s)
        self._name = name
        self._store: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._stats = CacheStats()
        self._memory = 0  # running estimate

    # -- properties --

    @property
    def name(self) -> str:
        return self._name

    @property
    def max_entries(self) -> int:
        return self._max_entries

    @property
    def max_memory_bytes(self) -> int:
        return self._max_memory

    def count(self) -> int:
        with self._lock:
            return len(self._store)

    def stats(self) -> CacheStats:
        with self._lock:
            s = CacheStats(
                hits=self._stats.hits,
                misses=self._stats.misses,
                evictions=self._stats.evictions,
                expiries=self._stats.expiries,
                invalidations=self._stats.invalidations,
                entries=len(self._store),
                estimated_memory_bytes=self._memory,
            )
            return s

    # -- core ops --

    def _estimate_size(self, value: Any, explicit: Optional[int]) -> int:
        if explicit is not None and explicit > 0:
            return int(explicit)
        # best-effort: len*overhead for containers, sys.getsizeof fallback
        try:
            import sys
            return sys.getsizeof(value)
        except Exception:
            return 1024

    def _evict_if_needed(self) -> None:
        # evict LRU until within bounds
        while self._store and (len(self._store) > self._max_entries or self._memory > self._max_memory):
            k, entry = self._store.popitem(last=False)  # FIFO = LRU (we move_to_end on hit)
            self._memory = max(0, self._memory - entry.size_bytes)
            self._stats.evictions += 1

    def _purge_expired(self, now: float) -> int:
        expired_keys = [k for k, e in self._store.items() if e.is_expired(now)]
        for k in expired_keys:
            entry = self._store.pop(k)
            self._memory = max(0, self._memory - entry.size_bytes)
            self._stats.expiries += 1
        return len(expired_keys)

    def get(self, key: str, *, allow_expired: bool = False) -> Optional[CacheEntry]:
        """
        Return entry or None. Updates LRU order on hit.
        Expired entries are removed and counted as misses unless allow_expired.
        Caller must check entry.provenance / source_tick if provenance-sensitive.
        """
        if not isinstance(key, str) or not key:
            raise CacheError("cache key must be non-empty string", operation="get", resource=key)
        with self._lock:
            now = time.monotonic()
            entry = self._store.get(key)
            if entry is None:
                self._stats.misses += 1
                return None
            if entry.is_expired(now) and not allow_expired:
                # expire and treat as miss
                self._store.pop(key)
                self._memory = max(0, self._memory - entry.size_bytes)
                self._stats.expiries += 1
                self._stats.misses += 1
                return None
            # hit -> move to end (MRU)
            self._store.move_to_end(key)
            self._stats.hits += 1
            return entry

    def get_value(self, key: str) -> Optional[Any]:
        e = self.get(key)
        return e.clone_value() if e else None

    def put(
        self,
        key: str,
        value: Any,
        *,
        ttl_s: Optional[float] = None,
        provenance: str = "derived",
        source_tick: int = -1,
        tags: Optional[Set[str]] = None,
        size_bytes: Optional[int] = None,
    ) -> None:
        if not isinstance(key, str) or not key:
            raise CacheError("cache key must be non-empty string", operation="put", resource=key)
        if ttl_s is not None and not isinstance(ttl_s, (int, float)):
            raise CacheError("ttl_s must be numeric", operation="put", resource=key)
        ttl = float(ttl_s) if ttl_s is not None else self._default_ttl
        if ttl < 0 or ttl > 86400:
            raise CacheError(f"ttl_s must be in [0, 86400], got {ttl}", operation="put", resource=key)
        with self._lock:
            now = time.monotonic()
            self._purge_expired(now)
            sz = self._estimate_size(value, size_bytes)
            entry = CacheEntry(
                value=value,
                provenance=str(provenance),
                source_tick=int(source_tick),
                created_monotonic=now,
                ttl_s=ttl,
                tags=set(tags) if tags else set(),
                size_bytes=sz,
            )
            if key in self._store:
                old = self._store.pop(key)
                self._memory = max(0, self._memory - old.size_bytes)
            self._store[key] = entry
            self._store.move_to_end(key)
            self._memory += sz
            self._evict_if_needed()

    def get_or_compute(
        self,
        key: str,
        compute: Callable[[], Any],
        *,
        ttl_s: Optional[float] = None,
        provenance: str = "derived",
        source_tick: int = -1,
        tags: Optional[Set[str]] = None,
        size_bytes: Optional[int] = None,
    ) -> Any:
        """
        Cache-aside helper with explicit compute. compute() is only called on
        miss/expiry. compute() must not mutate simulation state (enforced by caller).
        """
        e = self.get(key)
        if e is not None:
            return e.clone_value()
        # miss: compute outside lock to avoid blocking
        value = compute()
        self.put(key, value, ttl_s=ttl_s, provenance=provenance, source_tick=source_tick, tags=tags, size_bytes=size_bytes)
        return value

    # -- invalidation --

    def invalidate(self, key: str) -> bool:
        if not isinstance(key, str) or not key:
            raise CacheError("invalidate key must be non-empty string", operation="invalidate", resource=key)
        with self._lock:
            entry = self._store.pop(key, None)
            if entry is None:
                return False
            self._memory = max(0, self._memory - entry.size_bytes)
            self._stats.invalidations += 1
            return True

    def invalidate_prefix(self, prefix: str) -> int:
        if not isinstance(prefix, str) or not prefix:
            raise CacheError("invalidate prefix must be non-empty string", operation="invalidate_prefix", resource=prefix)
        with self._lock:
            keys = [k for k in self._store if k.startswith(prefix)]
            for k in keys:
                entry = self._store.pop(k)
                self._memory = max(0, self._memory - entry.size_bytes)
                self._stats.invalidations += 1
            return len(keys)

    def invalidate_tags(self, tags: Set[str]) -> int:
        if not isinstance(tags, set):
            raise CacheError("tags must be set", operation="invalidate_tags")
        with self._lock:
            keys = [k for k, e in self._store.items() if e.tags & tags]
            for k in keys:
                entry = self._store.pop(k)
                self._memory = max(0, self._memory - entry.size_bytes)
                self._stats.invalidations += 1
            return len(keys)

    def invalidate_provenance(self, provenance: str) -> int:
        with self._lock:
            keys = [k for k, e in self._store.items() if e.provenance == provenance]
            for k in keys:
                entry = self._store.pop(k)
                self._memory = max(0, self._memory - entry.size_bytes)
                self._stats.invalidations += 1
            return len(keys)

    def clear(self) -> int:
        with self._lock:
            n = len(self._store)
            self._store.clear()
            self._memory = 0
            self._stats.invalidations += n
            return n

    # -- inspection --

    def keys(self) -> List[str]:
        with self._lock:
            # purge expired first so keys reflects live view
            self._purge_expired(time.monotonic())
            return list(self._store.keys())

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "name": self._name,
                "max_entries": self._max_entries,
                "max_memory_bytes": self._max_memory,
                "default_ttl_s": self._default_ttl,
                "stats": self.stats().to_dict(),
            }


class CacheRegistry:
    """
    Registry of scoped caches — one per subsystem/lifetime.

    Prevents accidental global cache that outlives its owner.
    """

    def __init__(self):
        self._caches: Dict[str, BoundedCache] = {}
        self._lock = threading.Lock()

    def get_or_create(self, name: str, **kwargs) -> BoundedCache:
        with self._lock:
            if name in self._caches:
                return self._caches[name]
            c = BoundedCache(name=name, **kwargs)
            self._caches[name] = c
            return c

    def get(self, name: str) -> Optional[BoundedCache]:
        with self._lock:
            return self._caches.get(name)

    def remove(self, name: str) -> bool:
        with self._lock:
            cache = self._caches.pop(name, None)
            if cache:
                cache.clear()
                return True
            return False

    def clear_all(self) -> None:
        with self._lock:
            for c in self._caches.values():
                c.clear()
            self._caches.clear()

    def stats_summary(self) -> Dict[str, Any]:
        with self._lock:
            return {name: c.stats().to_dict() for name, c in self._caches.items()}


__all__ = ["CacheEntry", "CacheStats", "BoundedCache", "CacheRegistry"]
