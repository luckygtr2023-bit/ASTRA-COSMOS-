"""ASTRA Core configuration management."""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
import json
import os


@dataclass
class Config:
    """ASTRA Core configuration."""

    # Engine settings
    engine_name: str = "ASTRA"
    max_ticks_per_second: float = 60.0
    default_tick_duration: float = 1.0 / 60.0

    # Threading
    use_dedicated_simulation_thread: bool = True
    simulation_thread_priority: int = 1

    # RNG
    global_seed: int = 42
    rng_stream_count: int = 16

    # Persistence
    persistence_enabled: bool = True
    persistence_path: str = "./astra_snapshots"
    auto_save_interval: int = 0  # 0 = disabled, otherwise ticks between saves
    checksum_enabled: bool = True

    # Logging
    log_level: str = "INFO"
    log_to_file: bool = False
    log_file_path: str = "./astra.log"

    # Recovery
    recovery_policy: str = "FAIL_FAST"  # FAIL_FAST, RETRY_STEP, DROP_EVENT
    max_retry_attempts: int = 3

    # Resources
    max_resource_handles: int = 10000
    resource_cleanup_interval: int = 100  # ticks

    # Custom extensions
    extensions: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Config":
        """Create a Config from a dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @classmethod
    def from_json(cls, path: str) -> "Config":
        """Load configuration from a JSON file."""
        with open(path, "r") as f:
            data = json.load(f)
        return cls.from_dict(data)

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to a dictionary."""
        return {
            field.name: getattr(self, field.name)
            for field in self.__dataclass_fields__.values()
        }

    def to_json(self, path: str):
        """Save configuration to a JSON file."""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by key."""
        return getattr(self, key, default)

    def set(self, key: str, value: Any):
        """Set a configuration value by key."""
        if hasattr(self, key):
            setattr(self, key, value)
        else:
            self.extensions[key] = value
