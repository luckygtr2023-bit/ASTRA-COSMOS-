# Copyright © 2026 Lucky Kumar — ASTRA COSMOS
"""Centralized Supabase configuration — single source, no hard-coding scattered.

Supports:
  ASTRA_SUPABASE_URL / ASTRA_SUPABASE_PUBLISHABLE_KEY (preferred)
  SUPABASE_URL / SUPABASE_PUBLISHABLE_KEY (fallback)
  SUPABASE_PUBLISHABLE_KEY vs SUPABASE_ANON_KEY (supabase-js compat)
  .env loading via python-dotenv if available, else manual .env parse
  Offline mode flag
"""
from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Optional

def _load_env_file(path: str = ".env") -> None:
    # Minimal .env loader without python-dotenv dependency
    try:
        # try python-dotenv first
        from dotenv import load_dotenv  # type: ignore
        load_dotenv(path, override=False)
        return
    except ImportError:
        pass
    try:
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line=line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k,v=line.split("=",1)
                k=k.strip(); v=v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k]=v
    except Exception:
        pass

_load_env_file(".env")
_load_env_file("/home/user/ASTRA-COSMOS-/.env")

@dataclass
class SupabaseConfig:
    url: str
    publishable_key: str
    offline_mode: bool = False
    timeout_ms: int = 5000

    @property
    def is_configured(self) -> bool:
        return bool(self.url and self.publishable_key and not self.offline_mode)

    @property
    def is_offline(self) -> bool:
        return self.offline_mode or not self.url or not self.publishable_key

_singleton: Optional[SupabaseConfig] = None

def get_config() -> SupabaseConfig:
    global _singleton
    if _singleton is not None:
        return _singleton
    # prefer ASTRA_ prefix, fallback to generic
    url = os.getenv("ASTRA_SUPABASE_URL") or os.getenv("SUPABASE_URL") or ""
    # support both PUBLISHABLE_KEY and ANON_KEY naming
    key = (
        os.getenv("ASTRA_SUPABASE_PUBLISHABLE_KEY")
        or os.getenv("ASTRA_SUPABASE_ANON_KEY")
        or os.getenv("SUPABASE_PUBLISHABLE_KEY")
        or os.getenv("SUPABASE_ANON_KEY")
        or os.getenv("SUPABASE_KEY")
        or ""
    )
    offline = (os.getenv("ASTRA_SUPABASE_OFFLINE_MODE") or "").lower() in ("1","true","yes")
    # also allow explicit disable via missing env — not offline unless requested
    try:
        timeout = int(os.getenv("ASTRA_SUPABASE_TIMEOUT_MS") or "5000")
    except ValueError:
        timeout = 5000
    # strip trailing slash
    url = url.rstrip("/")
    _singleton = SupabaseConfig(url=url, publishable_key=key, offline_mode=offline, timeout_ms=timeout)
    return _singleton

def reset_config_cache() -> None:
    global _singleton
    _singleton = None
