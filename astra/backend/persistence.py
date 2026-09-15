"""
ASTRA Backend — persistence integration (no second DB).

Delegates to astra.core.persistence.PersistenceManager for world state.
Adds versioned, explicit integrations for:
  - runtime state (ticks, recovery, health)
  - rendering config snapshot
  - graphics config snapshot
  - backend config (AstraBackendConfig) itself
  - ingestion manifest passthrough (never duplicates catalog tables)

All paths/modes validated; errors are explicit with resource/operation.

Spec §6, §12:
  - Integrates with existing persistence infrastructure
  - Handles simulation-related persistence appropriately
  - Clear separation of concerns
"""

from __future__ import annotations

import json
import hashlib
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from astra.core.persistence import PersistenceManager
from astra.core.exceptions import PersistenceError as CorePersistenceError

from astra.backend.exceptions import PersistenceIntegrationError, ConfigurationError


# -- helpers --

def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _hash_payload(payload: Dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Integration facade
# ---------------------------------------------------------------------------

class BackendPersistence:
    """
    Persistence integration layer.

    Owns NO database itself if possible — delegates world snapshots to
    PersistenceManager. For backend-owned JSON snapshots (render/graphics
    config, diagnostics), uses deterministic file I/O under a single
    root so operations remain auditable and not competing with world DB.
    """

    def __init__(
        self,
        persistence_manager: Optional[PersistenceManager] = None,
        *,
        backend_root: str | Path = "backend_state",
        world_db_hint: Optional[str] = None,
    ):
        # reuse or create the single PM
        self._pm: PersistenceManager = persistence_manager or PersistenceManager()
        self._root = Path(backend_root)
        self._world_db_hint = world_db_hint
        self._lock = threading.RLock()
        # ensure root exists lazily

    @property
    def persistence_manager(self) -> PersistenceManager:
        return self._pm

    @property
    def backend_root(self) -> Path:
        return self._root

    # -- world state (delegated, never duplicated) --

    def save_world_state(self, world: Any) -> bool:
        """
        Delegate to PM.save_world_state. Enforces finite state checks via PM.
        Returns bool success.

        world must be an astra.world.World instance (validated by PM).
        """
        try:
            return self._pm.save_world_state(world)
        except CorePersistenceError as e:
            raise PersistenceIntegrationError(str(e), operation="save_world_state", resource="world", cause=e, recoverable=False)
        except Exception as e:
            raise PersistenceIntegrationError(f"save_world_state failed: {e}", operation="save_world_state", resource="world", cause=e, recoverable=False)

    def load_world_state(self) -> Optional[Any]:
        try:
            return self._pm.load_world_state()
        except CorePersistenceError as e:
            raise PersistenceIntegrationError(str(e), operation="load_world_state", resource="world", cause=e, recoverable=True)
        except Exception as e:
            raise PersistenceIntegrationError(f"load_world_state failed: {e}", operation="load_world_state", resource="world", cause=e, recoverable=True)

    def save_checkpoint(self, label: str, payload: Dict[str, Any]) -> Path:
        """
        Save an opaque JSON checkpoint under backend_root/checkpoints/<label>.json.
        Label validated; payload must be JSON serializable; deterministic keys.
        """
        if not isinstance(label, str) or not label or "/" in label or "\\" in label:
            raise PersistenceIntegrationError(f"invalid checkpoint label {label!r}", operation="save_checkpoint", resource=label)
        try:
            json.dumps(payload, sort_keys=True)  # validate
        except Exception as e:
            raise PersistenceIntegrationError(f"checkpoint payload not JSON serializable: {e}", operation="save_checkpoint", resource=label, cause=e)

        with self._lock:
            _ensure_parent(self._root / "checkpoints" / f"{label}.json")
            path = self._root / "checkpoints" / f"{label}.json"
            tmp = path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")
            tmp.replace(path)
            return path

    def load_checkpoint(self, label: str) -> Optional[Dict[str, Any]]:
        if not isinstance(label, str) or not label:
            raise PersistenceIntegrationError(f"invalid label {label!r}", operation="load_checkpoint", resource=label)
        path = self._root / "checkpoints" / f"{label}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            raise PersistenceIntegrationError(f"failed to load checkpoint {label}: {e}", operation="load_checkpoint", resource=str(path), cause=e, recoverable=True)

    def list_checkpoints(self) -> List[str]:
        root = self._root / "checkpoints"
        if not root.exists():
            return []
        return sorted(p.stem for p in root.glob("*.json"))

    # -- config snapshots (versioned) --

    def save_backend_config(self, config: Any, *, label: str = "active") -> Path:
        """
        Save an AstraBackendConfig snapshot (validated).
        """
        # Lazy import to avoid circular
        from astra.backend.config import AstraBackendConfig
        if not isinstance(config, AstraBackendConfig):
            raise PersistenceIntegrationError(f"config must be AstraBackendConfig, got {type(config).__name__}", operation="save_backend_config", resource=label)
        config.validate()
        d = config.to_dict()
        payload = {"schema_version": d.get("schema_version", 1), "fingerprint": config.fingerprint(), "config": d}
        return self.save_checkpoint(f"config_{label}", payload)

    def load_backend_config(self, label: str = "active") -> Optional[Any]:
        from astra.backend.config import AstraBackendConfig
        doc = self.load_checkpoint(f"config_{label}")
        if doc is None:
            return None
        cfg_dict = doc.get("config") if isinstance(doc, dict) else None
        if not isinstance(cfg_dict, dict):
            raise PersistenceIntegrationError(f"checkpoint config_{label} malformed", operation="load_backend_config", resource=label)
        try:
            return AstraBackendConfig.from_dict(cfg_dict)
        except ConfigurationError as e:
            raise PersistenceIntegrationError(str(e), operation="load_backend_config", resource=label, cause=e)
        except Exception as e:
            raise PersistenceIntegrationError(f"load_backend_config failed: {e}", operation="load_backend_config", resource=label, cause=e)

    # -- runtime diagnostics snapshot --

    def save_runtime_snapshot(self, snapshot: Dict[str, Any], tick: int) -> Path:
        if not isinstance(tick, int) or tick < 0:
            raise PersistenceIntegrationError(f"tick must be int >=0, got {tick!r}", operation="save_runtime_snapshot", resource=str(tick))
        label = f"runtime_tick_{tick:08d}_{_hash_payload(snapshot)}"
        return self.save_checkpoint(label, {"tick": tick, "snapshot": snapshot})

    # -- render/graphics config delegation (not world DB) --

    def save_render_config(self, pipeline_config: Any) -> Path:
        """Save a rendering PipelineConfig snapshot deterministically."""
        try:
            if hasattr(pipeline_config, "to_dict"):
                d = pipeline_config.to_dict()  # type: ignore
            elif hasattr(pipeline_config, "__dataclass_fields__"):
                import dataclasses
                # handle dataclass PipelineConfig via asdict (nested)
                try:
                    d = dataclasses.asdict(pipeline_config)
                except Exception:
                    d = {k: getattr(pipeline_config, k) for k in pipeline_config.__dataclass_fields__}
                # ensure enums/stringified deterministically
                d = json.loads(json.dumps(d, sort_keys=True, default=str))
            else:
                d = dict(pipeline_config)  # type: ignore
        except Exception as e:
            raise PersistenceIntegrationError(f"render config not serializable: {e}", operation="save_render_config", cause=e)
        return self.save_checkpoint("render_pipeline", {"pipeline": d})

    def load_render_config(self) -> Optional[Dict[str, Any]]:
        doc = self.load_checkpoint("render_pipeline")
        if doc is None:
            return None
        return doc.get("pipeline")

    # -- diagnostics helpers --

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            n_checkpoints = len(self.list_checkpoints())
            pm = self._pm
            pm_stats = {}
            try:
                # PersistenceManager may expose save_count etc via diagnostics
                pm_stats = {"exists": bool(self._root.exists())}
            except Exception:
                pass
            return {"backend_root": str(self._root), "checkpoints": n_checkpoints, "pm": pm_stats}


__all__ = ["BackendPersistence"]
