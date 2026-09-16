"""Supabase client abstraction — client-safe, offline-tolerant, no service_role.

Design:
 - Client-safe: only SUPABASE_URL + PUBLISHABLE_KEY (anon), never service_role.
 - Offline: is_available() false → simulator continues, product features disabled.
 - Single import point, not scattered.
 - Lazy import of supabase-py; mock fallback if not installed or offline.
"""
from __future__ import annotations
import os
from typing import Optional, Any
from .config import get_config, SupabaseConfig

class MockSupabaseClient:
    """Fallback when supabase package missing or offline — keeps simulator functional."""
    def __init__(self, config: SupabaseConfig):
        self.config = config
        self._mock = True
    def is_mock(self) -> bool:
        return True
    def __repr__(self) -> str:
        return f"<MockSupabaseClient offline={self.config.is_offline} url={self.config.url[:30] if self.config.url else 'none'}>"

class SupabaseClient:
    def __init__(self, config: Optional[SupabaseConfig]=None):
        self.config = config or get_config()
        self._client: Optional[Any] = None
        self._mock_client: Optional[MockSupabaseClient] = None
        self._init_error: Optional[str] = None
        if self.config.is_offline:
            self._mock_client = MockSupabaseClient(self.config)
        else:
            try:
                # prefer supabase-py >=2
                from supabase import create_client  # type: ignore
                if self.config.url and self.config.publishable_key:
                    self._client = create_client(self.config.url, self.config.publishable_key)
                else:
                    self._init_error = "missing url/key"
                    self._mock_client = MockSupabaseClient(self.config)
            except Exception as e:
                self._init_error = str(e)
                self._mock_client = MockSupabaseClient(self.config)

    @property
    def is_available(self) -> bool:
        return self._client is not None and not self.config.is_offline

    @property
    def is_mock(self) -> bool:
        return self._mock_client is not None

    @property
    def native(self) -> Optional[Any]:
        return self._client

    def health(self) -> dict:
        return {
            "configured": self.config.is_configured,
            "offline": self.config.is_offline,
            "available": self.is_available,
            "mock": self.is_mock,
            "url": self.config.url,
            "error": self._init_error,
            # never expose keys
        }

_client_singleton: Optional[SupabaseClient] = None

def get_client() -> SupabaseClient:
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = SupabaseClient()
    return _client_singleton

def is_available() -> bool:
    return get_client().is_available

def reset_client_cache() -> None:
    global _client_singleton
    _client_singleton = None
