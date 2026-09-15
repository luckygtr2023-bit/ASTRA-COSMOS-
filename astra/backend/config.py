"""
ASTRA Backend — unified configuration.

Integrates without bypassing astra.core.config:
  simulation (Engine/World/Time), persistence paths,
  service timeouts, recovery policy.

Adds rendering / graphics / runtime / cache / diagnostics
sections needed by §5-§12 of the integration spec.

Contracts:
  - Validated (finite numbers, positive budgets, allowed enums)
  - Deterministic serialization (sorted keys, stable defaults)
  - Versionable (schema_version, migration via from_dict)
  - Explicit defaults (no hidden side-effects on load failure)
  - Never mutates authoritative simulation config at runtime
"""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from astra.core.config import Config as CoreConfig
from astra.core.recovery import RecoveryPolicy

from astra.backend.exceptions import ConfigurationError


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class RenderQualityPreset(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    ULTRA = "ULTRA"
    AUTO = "AUTO"


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


# ---------------------------------------------------------------------------
# Validated helpers
# ---------------------------------------------------------------------------

def _require_finite(v: float, name: str, low: Optional[float] = None, high: Optional[float] = None) -> float:
    if not isinstance(v, (int, float)):
        raise ConfigurationError(f"{name} must be numeric, got {type(v).__name__}", operation="validate", resource=name)
    fv = float(v)
    import math
    if not math.isfinite(fv):
        raise ConfigurationError(f"{name} must be finite, got {fv!r}", operation="validate", resource=name)
    if low is not None and fv < low:
        raise ConfigurationError(f"{name} must be >= {low}, got {fv}", operation="validate", resource=name)
    if high is not None and fv > high:
        raise ConfigurationError(f"{name} must be <= {high}, got {fv}", operation="validate", resource=name)
    return fv


def _require_int(v: int, name: str, low: Optional[int] = None, high: Optional[int] = None) -> int:
    if not isinstance(v, int) or isinstance(v, bool):
        raise ConfigurationError(f"{name} must be int, got {type(v).__name__}", operation="validate", resource=name)
    if low is not None and v < low:
        raise ConfigurationError(f"{name} must be >= {low}, got {v}", operation="validate", resource=name)
    if high is not None and v > high:
        raise ConfigurationError(f"{name} must be > {high} if set", operation="validate", resource=name)
    return v


# ---------------------------------------------------------------------------
# Section configs
# ---------------------------------------------------------------------------

@dataclass
class RenderingConfig:
    """Rendering integration settings (maps to astra.rendering.PipelineConfig)."""
    quality: RenderQualityPreset = RenderQualityPreset.MEDIUM
    max_visible_objects: int = 5000
    max_memory_mb: float = 512.0
    enable_floating_origin: bool = True
    enable_shadows: bool = True
    lod_bias: float = 1.0
    max_distance_m: float = 1e15  # large-scale: interplanetary / interstellar

    def validate(self) -> None:
        _require_int(self.max_visible_objects, "rendering.max_visible_objects", low=1, high=200_000)
        _require_finite(self.max_memory_mb, "rendering.max_memory_mb", low=1.0, high=32768.0)
        _require_finite(self.lod_bias, "rendering.lod_bias", low=0.1, high=10.0)
        _require_finite(self.max_distance_m, "rendering.max_distance_m", low=1.0)
        if not isinstance(self.quality, RenderQualityPreset):
            raise ConfigurationError(f"rendering.quality must be RenderQualityPreset, got {self.quality!r}", operation="validate", resource="rendering.quality")

    def clone(self) -> "RenderingConfig":
        return RenderingConfig(
            quality=self.quality,
            max_visible_objects=self.max_visible_objects,
            max_memory_mb=self.max_memory_mb,
            enable_floating_origin=self.enable_floating_origin,
            enable_shadows=self.enable_shadows,
            lod_bias=self.lod_bias,
            max_distance_m=self.max_distance_m,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "quality": self.quality.value,
            "max_visible_objects": self.max_visible_objects,
            "max_memory_mb": self.max_memory_mb,
            "enable_floating_origin": self.enable_floating_origin,
            "enable_shadows": self.enable_shadows,
            "lod_bias": self.lod_bias,
            "max_distance_m": self.max_distance_m,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RenderingConfig":
        try:
            q = RenderQualityPreset(d.get("quality", "MEDIUM"))
        except ValueError as e:
            raise ConfigurationError(f"unknown quality {d.get('quality')!r}", operation="from_dict", resource="rendering.quality", cause=e)
        c = cls(
            quality=q,
            max_visible_objects=int(d.get("max_visible_objects", 5000)),
            max_memory_mb=float(d.get("max_memory_mb", 512.0)),
            enable_floating_origin=bool(d.get("enable_floating_origin", True)),
            enable_shadows=bool(d.get("enable_shadows", True)),
            lod_bias=float(d.get("lod_bias", 1.0)),
            max_distance_m=float(d.get("max_distance_m", 1e15)),
        )
        c.validate()
        return c


@dataclass
class GraphicsConfig:
    """Graphics/VFX placeholder config (no shader compilation here)."""
    enabled: bool = False
    backend: str = "placeholder"  # future: "blender", "vulkan", etc.
    max_materials: int = 4096
    max_textures_mb: int = 1024

    def validate(self) -> None:
        if not isinstance(self.backend, str) or not self.backend:
            raise ConfigurationError("graphics.backend must be non-empty string", operation="validate", resource="graphics.backend")
        _require_int(self.max_materials, "graphics.max_materials", low=1, high=1_000_000)
        _require_int(self.max_textures_mb, "graphics.max_textures_mb", low=1, high=32768)

    def clone(self) -> "GraphicsConfig":
        return GraphicsConfig(enabled=self.enabled, backend=self.backend, max_materials=self.max_materials, max_textures_mb=self.max_textures_mb)

    def to_dict(self) -> Dict[str, Any]:
        return {"enabled": self.enabled, "backend": self.backend, "max_materials": self.max_materials, "max_textures_mb": self.max_textures_mb}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GraphicsConfig":
        c = cls(
            enabled=bool(d.get("enabled", False)),
            backend=str(d.get("backend", "placeholder")),
            max_materials=int(d.get("max_materials", 4096)),
            max_textures_mb=int(d.get("max_textures_mb", 1024)),
        )
        c.validate()
        return c


@dataclass
class RuntimeConfig:
    recovery_policy: RecoveryPolicy = RecoveryPolicy.FAIL_FAST
    max_retry_attempts: int = 3
    service_timeout_s: float = 5.0
    heartbeat_interval_s: float = 1.0
    allow_concurrent_reads: bool = True  # rendering may read concurrently; never write

    def validate(self) -> None:
        if not isinstance(self.recovery_policy, RecoveryPolicy):
            raise ConfigurationError(f"runtime.recovery_policy must be RecoveryPolicy, got {self.recovery_policy!r}", operation="validate", resource="runtime.recovery_policy")
        _require_int(self.max_retry_attempts, "runtime.max_retry_attempts", low=0, high=100)
        _require_finite(self.service_timeout_s, "runtime.service_timeout_s", low=0.01, high=3600.0)
        _require_finite(self.heartbeat_interval_s, "runtime.heartbeat_interval_s", low=0.05, high=3600.0)

    def clone(self) -> "RuntimeConfig":
        return RuntimeConfig(
            recovery_policy=self.recovery_policy,
            max_retry_attempts=self.max_retry_attempts,
            service_timeout_s=self.service_timeout_s,
            heartbeat_interval_s=self.heartbeat_interval_s,
            allow_concurrent_reads=self.allow_concurrent_reads,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recovery_policy": self.recovery_policy.value,
            "max_retry_attempts": self.max_retry_attempts,
            "service_timeout_s": self.service_timeout_s,
            "heartbeat_interval_s": self.heartbeat_interval_s,
            "allow_concurrent_reads": self.allow_concurrent_reads,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RuntimeConfig":
        pol = d.get("recovery_policy", "fail_fast")
        try:
            rp = RecoveryPolicy(pol)
        except ValueError as e:
            raise ConfigurationError(f"unknown recovery policy {pol!r}", operation="from_dict", resource="runtime.recovery_policy", cause=e)
        c = cls(
            recovery_policy=rp,
            max_retry_attempts=int(d.get("max_retry_attempts", 3)),
            service_timeout_s=float(d.get("service_timeout_s", 5.0)),
            heartbeat_interval_s=float(d.get("heartbeat_interval_s", 1.0)),
            allow_concurrent_reads=bool(d.get("allow_concurrent_reads", True)),
        )
        c.validate()
        return c


@dataclass
class CacheConfig:
    enabled: bool = True
    max_entries: int = 2048
    max_memory_mb: float = 256.0
    default_ttl_s: float = 30.0
    enforce_provenance: bool = True  # never cache stale authoritative data as authoritative

    def validate(self) -> None:
        _require_int(self.max_entries, "cache.max_entries", low=1, high=1_000_000)
        _require_finite(self.max_memory_mb, "cache.max_memory_mb", low=1.0, high=32768.0)
        _require_finite(self.default_ttl_s, "cache.default_ttl_s", low=0.0, high=86400.0)

    def clone(self) -> "CacheConfig":
        return CacheConfig(enabled=self.enabled, max_entries=self.max_entries, max_memory_mb=self.max_memory_mb, default_ttl_s=self.default_ttl_s, enforce_provenance=self.enforce_provenance)

    def to_dict(self) -> Dict[str, Any]:
        return {"enabled": self.enabled, "max_entries": self.max_entries, "max_memory_mb": self.max_memory_mb, "default_ttl_s": self.default_ttl_s, "enforce_provenance": self.enforce_provenance}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CacheConfig":
        c = cls(
            enabled=bool(d.get("enabled", True)),
            max_entries=int(d.get("max_entries", 2048)),
            max_memory_mb=float(d.get("max_memory_mb", 256.0)),
            default_ttl_s=float(d.get("default_ttl_s", 30.0)),
            enforce_provenance=bool(d.get("enforce_provenance", True)),
        )
        c.validate()
        return c


@dataclass
class PersistenceBackendConfig:
    """Paths / options that delegate to core persistence; no second DB."""
    world_db_path: Optional[str] = None  # None => use core default
    archive_db_path: Optional[str] = None
    enable_auto_checkpoint: bool = False
    checkpoint_interval_ticks: int = 100

    def validate(self) -> None:
        if self.world_db_path is not None and not isinstance(self.world_db_path, str):
            raise ConfigurationError("persistence.world_db_path must be str or None", operation="validate", resource="persistence.world_db_path")
        if self.archive_db_path is not None and not isinstance(self.archive_db_path, str):
            raise ConfigurationError("persistence.archive_db_path must be str or None", operation="validate", resource="persistence.archive_db_path")
        _require_int(self.checkpoint_interval_ticks, "persistence.checkpoint_interval_ticks", low=1, high=1_000_000)

    def clone(self) -> "PersistenceBackendConfig":
        return PersistenceBackendConfig(world_db_path=self.world_db_path, archive_db_path=self.archive_db_path, enable_auto_checkpoint=self.enable_auto_checkpoint, checkpoint_interval_ticks=self.checkpoint_interval_ticks)

    def to_dict(self) -> Dict[str, Any]:
        return {"world_db_path": self.world_db_path, "archive_db_path": self.archive_db_path, "enable_auto_checkpoint": self.enable_auto_checkpoint, "checkpoint_interval_ticks": self.checkpoint_interval_ticks}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PersistenceBackendConfig":
        c = cls(
            world_db_path=d.get("world_db_path"),
            archive_db_path=d.get("archive_db_path"),
            enable_auto_checkpoint=bool(d.get("enable_auto_checkpoint", False)),
            checkpoint_interval_ticks=int(d.get("checkpoint_interval_ticks", 100)),
        )
        c.validate()
        return c


@dataclass
class DiagnosticsConfig:
    enabled: bool = True
    log_level: LogLevel = LogLevel.INFO
    collect_metrics: bool = True
    max_log_entries: int = 10000

    def validate(self) -> None:
        if not isinstance(self.log_level, LogLevel):
            raise ConfigurationError(f"diagnostics.log_level must be LogLevel, got {self.log_level!r}", operation="validate", resource="diagnostics.log_level")
        _require_int(self.max_log_entries, "diagnostics.max_log_entries", low=1, high=1_000_000)

    def clone(self) -> "DiagnosticsConfig":
        return DiagnosticsConfig(enabled=self.enabled, log_level=self.log_level, collect_metrics=self.collect_metrics, max_log_entries=self.max_log_entries)

    def to_dict(self) -> Dict[str, Any]:
        return {"enabled": self.enabled, "log_level": self.log_level.value, "collect_metrics": self.collect_metrics, "max_log_entries": self.max_log_entries}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DiagnosticsConfig":
        lvl = d.get("log_level", "INFO")
        try:
            ll = LogLevel(lvl)
        except ValueError as e:
            raise ConfigurationError(f"unknown log level {lvl!r}", operation="from_dict", resource="diagnostics.log_level", cause=e)
        c = cls(enabled=bool(d.get("enabled", True)), log_level=ll, collect_metrics=bool(d.get("collect_metrics", True)), max_log_entries=int(d.get("max_log_entries", 10000)))
        c.validate()
        return c


# ---------------------------------------------------------------------------
# Top-level unified config
# ---------------------------------------------------------------------------

BACKEND_SCHEMA_VERSION = 1


@dataclass
class AstraBackendConfig:
    """
    Unified backend/runtime integration configuration.

    Authoritative simulation config lives in astra.core.config.Config;
    this layer *references* it and owns rendering/graphics/runtime/cache
    integration concerns.

    No operation here mutates simulation state; validation is pure.
    """
    schema_version: int = BACKEND_SCHEMA_VERSION
    core: CoreConfig = field(default_factory=CoreConfig)
    rendering: RenderingConfig = field(default_factory=RenderingConfig)
    graphics: GraphicsConfig = field(default_factory=GraphicsConfig)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    persistence: PersistenceBackendConfig = field(default_factory=PersistenceBackendConfig)
    diagnostics: DiagnosticsConfig = field(default_factory=DiagnosticsConfig)
    # feature flags for future bridges (explicit, documented)
    feature_flags: Dict[str, bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _require_int(self.schema_version, "schema_version", low=1, high=100)
        # core validate: CoreConfig has no explicit validate method — sanity check its fields
        try:
            if hasattr(self.core, "validate"):
                self.core.validate()  # type: ignore[attr-defined]
            else:
                # basic sanity: ensure core serializes deterministically and required fields exist
                d = self.core.to_dict()
                if not isinstance(d, dict):
                    raise ConfigurationError("core.to_dict must return dict")
        except ConfigurationError:
            raise
        except Exception as e:
            raise ConfigurationError(f"core config invalid: {e}", operation="validate", resource="core", cause=e)
        self.rendering.validate()
        self.graphics.validate()
        self.runtime.validate()
        self.cache.validate()
        self.persistence.validate()
        self.diagnostics.validate()
        if not isinstance(self.feature_flags, dict):
            raise ConfigurationError("feature_flags must be dict", operation="validate", resource="feature_flags")
        for k, v in self.feature_flags.items():
            if not isinstance(k, str) or not k:
                raise ConfigurationError(f"feature_flags key must be non-empty str, got {k!r}", operation="validate", resource="feature_flags")
            if not isinstance(v, bool):
                raise ConfigurationError(f"feature_flags[{k!r}] must be bool, got {type(v).__name__}", operation="validate", resource="feature_flags")

    # -- immutability helpers --

    def _clone_core(self) -> CoreConfig:
        # CoreConfig may not have clone; use to_dict/from_dict roundtrip
        if hasattr(self.core, "clone"):
            return self.core.clone()  # type: ignore[attr-defined]
        return CoreConfig.from_dict(self.core.to_dict())

    def clone(self) -> "AstraBackendConfig":
        """Deep clone (isolated)."""
        return AstraBackendConfig(
            schema_version=self.schema_version,
            core=self._clone_core(),
            rendering=self.rendering.clone(),
            graphics=self.graphics.clone(),
            runtime=self.runtime.clone(),
            cache=self.cache.clone(),
            persistence=self.persistence.clone(),
            diagnostics=self.diagnostics.clone(),
            feature_flags=dict(self.feature_flags),
        )

    # -- deterministic serialization --

    def to_dict(self) -> Dict[str, Any]:
        """Deterministic dict (sorted keys when dumped)."""
        return {
            "schema_version": self.schema_version,
            "core": self.core.to_dict(),
            "rendering": self.rendering.to_dict(),
            "graphics": self.graphics.to_dict(),
            "runtime": self.runtime.to_dict(),
            "cache": self.cache.to_dict(),
            "persistence": self.persistence.to_dict(),
            "diagnostics": self.diagnostics.to_dict(),
            "feature_flags": dict(sorted(self.feature_flags.items())),
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, indent=indent)

    def fingerprint(self) -> str:
        """Stable SHA-256 of serialized config (for cache keys / diagnostics)."""
        payload = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:16]

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AstraBackendConfig":
        if not isinstance(d, dict):
            raise ConfigurationError(f"config dict must be dict, got {type(d).__name__}", operation="from_dict", resource="config")
        ver = int(d.get("schema_version", BACKEND_SCHEMA_VERSION))
        if ver != BACKEND_SCHEMA_VERSION:
            # Future: migrate; for now fail explicitly (no silent coercion)
            raise ConfigurationError(f"unsupported schema_version {ver}, expected {BACKEND_SCHEMA_VERSION}", operation="from_dict", resource="schema_version")
        try:
            core = CoreConfig.from_dict(d.get("core", {})) if "core" in d else CoreConfig()
        except Exception as e:
            raise ConfigurationError(f"core config parse failed: {e}", operation="from_dict", resource="core", cause=e)
        cfg = cls(
            schema_version=ver,
            core=core,
            rendering=RenderingConfig.from_dict(d.get("rendering", {})),
            graphics=GraphicsConfig.from_dict(d.get("graphics", {})),
            runtime=RuntimeConfig.from_dict(d.get("runtime", {})),
            cache=CacheConfig.from_dict(d.get("cache", {})),
            persistence=PersistenceBackendConfig.from_dict(d.get("persistence", {})),
            diagnostics=DiagnosticsConfig.from_dict(d.get("diagnostics", {})),
            feature_flags=dict(d.get("feature_flags", {})),
        )
        cfg.validate()
        return cfg

    @classmethod
    def from_json(cls, s: str) -> "AstraBackendConfig":
        try:
            d = json.loads(s)
        except Exception as e:
            raise ConfigurationError(f"invalid JSON: {e}", operation="from_json", resource="config", cause=e)
        return cls.from_dict(d)

    # -- persistence of config itself (versioned) --

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(self.to_json(), encoding="utf-8")
        tmp.replace(p)

    @classmethod
    def load(cls, path: str | Path) -> "AstraBackendConfig":
        p = Path(path)
        if not p.exists():
            raise ConfigurationError(f"config file not found: {p}", operation="load", resource=str(p))
        try:
            txt = p.read_text(encoding="utf-8")
        except Exception as e:
            raise ConfigurationError(f"failed to read {p}: {e}", operation="load", resource=str(p), cause=e)
        return cls.from_json(txt)

    # -- deterministic pipeline mapping --

    def to_pipeline_config(self):
        """Map rendering section to astra.rendering.PipelineConfig (deterministic)."""
        from astra.rendering.pipeline import PipelineConfig as RenderPipelineConfig
        from astra.rendering.lod import LODConfig
        from astra.rendering.culling import CullingConfig
        from astra.rendering.performance import PerformanceBudget
        from astra.rendering.types import QualityLevel as RQ

        # Map quality preset to rendering QualityLevel
        quality_map = {
            RenderQualityPreset.LOW: RQ.LOW,
            RenderQualityPreset.MEDIUM: RQ.MEDIUM,
            RenderQualityPreset.HIGH: RQ.HIGH,
            RenderQualityPreset.ULTRA: RQ.ULTRA,
            RenderQualityPreset.AUTO: RQ.AUTO,
        }
        q = quality_map[self.rendering.quality]
        # LODConfig uses global_bias as scale factor (higher = more detailed)
        # Our lod_bias follows quality bias intuition: lower bias = degraded (more impostor/cull).
        # Invert: global_bias = 1/lod_bias? Actually lod world uses bias divider; we map 1.0 -> 1.0,
        # 0.5 (ULTRA) should be more detailed => global_bias >1, so invert.
        lod_bias = float(self.rendering.lod_bias)
        global_bias = 1.0 / max(0.1, lod_bias)
        lod_cfg = LODConfig(global_bias=global_bias)
        return RenderPipelineConfig(
            lod_config=lod_cfg,
            culling_config=CullingConfig(max_distance_m=self.rendering.max_distance_m),
            performance_budget=PerformanceBudget(
                max_visible_objects=self.rendering.max_visible_objects,
                max_memory_mb=self.rendering.max_memory_mb,
            ),
            default_quality=q,
            enable_floating_origin=self.rendering.enable_floating_origin,
        )


__all__ = [
    "RenderQualityPreset",
    "LogLevel",
    "RenderingConfig",
    "GraphicsConfig",
    "RuntimeConfig",
    "CacheConfig",
    "PersistenceBackendConfig",
    "DiagnosticsConfig",
    "AstraBackendConfig",
    "BACKEND_SCHEMA_VERSION",
]
