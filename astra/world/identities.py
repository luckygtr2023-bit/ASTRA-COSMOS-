"""ASTRA World - deterministic identity types.

Contract: Stable internal identifiers for worlds, scenes, and regions.
IDs are deterministic (no UUIDs, no RNG) to ensure reproducible simulations
and stable save files.
"""

from dataclasses import dataclass
import hashlib


@dataclass(frozen=True)
class WorldId:
    """Deterministic world identifier."""

    value: str

    @classmethod
    def generate(cls, name: str) -> "WorldId":
        """Generate a deterministic ID based on world name."""
        digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:16]
        return cls(f"world_{digest}")

    @classmethod
    def from_name(cls, name: str) -> "WorldId":
        """Create a world ID from a name."""
        return cls(f"world_{name}")


@dataclass(frozen=True)
class SceneId:
    """Deterministic scene identifier."""

    value: str

    @classmethod
    def generate(cls, world_id: str, scene_name: str) -> "SceneId":
        """Generate a deterministic ID based on world and scene name."""
        combined = f"{world_id}:{scene_name}"
        digest = hashlib.sha256(combined.encode("utf-8")).hexdigest()[:16]
        return cls(f"scene_{digest}")

    @classmethod
    def from_name(cls, name: str) -> "SceneId":
        """Create a scene ID from a name."""
        return cls(f"scene_{name}")


@dataclass(frozen=True)
class RegionId:
    """Deterministic region identifier."""

    value: str

    @classmethod
    def generate(cls, scene_id: str, region_name: str) -> "RegionId":
        """Generate a deterministic ID based on scene and region name."""
        combined = f"{scene_id}:{region_name}"
        digest = hashlib.sha256(combined.encode("utf-8")).hexdigest()[:16]
        return cls(f"region_{digest}")

    @classmethod
    def from_name(cls, name: str) -> "RegionId":
        """Create a region ID from a name."""
        return cls(f"region_{name}")
