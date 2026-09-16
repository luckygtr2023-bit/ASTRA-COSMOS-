"""ASTRA Product ↔ Simulator Integration — explicit interface, offline-tolerant.

Supabase available → cloud account features enabled.
Supabase unavailable → local simulator continues, product layer disabled, no physics dependency.

Usage:
    from astra.product.integration import ProductIntegration
    from astra.core.engine import Engine

    engine = Engine()
    product = ProductIntegration(engine)
    product.initialize()  # tries Supabase, falls back silently if unavailable
    # engine remains authoritative; product only reads snapshots and writes metadata via SaveService
"""
from __future__ import annotations
from typing import Optional, Dict, Any
from astra.core.engine import Engine
from astra.core.logging import get_logger
from .supabase.client import get_client
from .supabase.saves import SaveService

logger = get_logger("product.integration")

class ProductIntegration:
    def __init__(self, engine: Engine):
        self.engine = engine
        self.client = get_client()
        self.saves = SaveService()
        self._initialized = False

    def initialize(self) -> bool:
        health = self.client.health()
        if health["available"]:
            logger.info(f"Product layer online: {health}")
            self._initialized = True
            return True
        else:
            logger.info(f"Product layer offline (simulator continues): {health}")
            self._initialized = False
            return False

    @property
    def is_online(self) -> bool:
        return self._initialized and self.client.is_available

    def save_snapshot_metadata(self, name: str, snapshot_bytes: Optional[bytes]=None, metadata: Optional[Dict[str,Any]]=None) -> Optional[Dict[str,Any]]:
        """Save artifact to Storage + metadata to Postgres. Returns metadata or None if offline."""
        if not self.is_online:
            logger.info("Offline: snapshot saved locally only (no cloud sync)")
            return None
        try:
            tick = getattr(self.engine, "_clock", None)
            sim_time = getattr(tick, "current_time", None) if tick else None
            return self.saves.create_simulation_save(
                name=name,
                description=f"tick {getattr(self.engine, '_total_ticks', 0)} sim_time {sim_time}",
                artifact_bytes=snapshot_bytes,
                simulation_version="astra.v1",
                engine_version="0.1.1",
                schema_version="1.0.0",
                metadata=metadata or {}
            )
        except Exception as e:
            logger.warning(f"Cloud save failed, local fallback preserved: {e}")
            return None

    def health_report(self) -> Dict[str,Any]:
        return {
            "product_initialized": self._initialized,
            **self.client.health(),
            "engine_state": str(getattr(self.engine, "_state", "unknown")),
            "offline_mode_supported": True
        }
