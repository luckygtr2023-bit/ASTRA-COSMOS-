"""ASTRA Core persistence system with atomic writes and integrity verification."""

import json
import hashlib
import os
import tempfile
import shutil
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, BinaryIO
from datetime import datetime, timezone
import threading

from astra.core.logging import get_logger
from astra.core.exceptions import PersistenceError


SCHEMA_VERSION = "1.0.0"
MAGIC_HEADER = b"ASTRA_SNAPSHOT_v1"
CHECKSUM_ALGORITHM = "sha256"


@dataclass
class Snapshot:
    """A simulation snapshot for persistence."""

    schema_version: str
    engine_state: Dict[str, Any]
    simulation_time: Dict[str, Any]
    entities: Dict[str, Any]
    frames: Dict[str, Any]
    rng_state: Dict[str, Any]
    command_history: List[Dict[str, Any]]
    event_history: List[Dict[str, Any]]
    tick: int
    timestamp: str = ""
    checksum: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def compute_checksum(self) -> str:
        """Compute the checksum of this snapshot (excluding the checksum field)."""
        data = {
            "schema_version": self.schema_version,
            "engine_state": self.engine_state,
            "simulation_time": self.simulation_time,
            "entities": self.entities,
            "frames": self.frames,
            "rng_state": self.rng_state,
            "command_history": self.command_history,
            "event_history": self.event_history,
            "tick": self.tick,
            "timestamp": self.timestamp,
        }
        json_data = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(json_data.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """Convert snapshot to dictionary."""
        return {
            "schema_version": self.schema_version,
            "engine_state": self.engine_state,
            "simulation_time": self.simulation_time,
            "entities": self.entities,
            "frames": self.frames,
            "rng_state": self.rng_state,
            "command_history": self.command_history,
            "event_history": self.event_history,
            "tick": self.tick,
            "timestamp": self.timestamp,
            "checksum": self.checksum,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Snapshot":
        """Create snapshot from dictionary."""
        return cls(
            schema_version=data.get("schema_version", ""),
            engine_state=data.get("engine_state", {}),
            simulation_time=data.get("simulation_time", {}),
            entities=data.get("entities", {}),
            frames=data.get("frames", {}),
            rng_state=data.get("rng_state", {}),
            command_history=data.get("command_history", []),
            event_history=data.get("event_history", []),
            tick=data.get("tick", 0),
            timestamp=data.get("timestamp", ""),
            checksum=data.get("checksum", ""),
        )


class PersistenceManager:
    """Manages simulation persistence with atomic writes and integrity verification."""

    def __init__(self, base_path: str = "./astra_snapshots", checksum_enabled: bool = True):
        self._base_path = base_path
        self._checksum_enabled = checksum_enabled
        self._lock = threading.Lock()
        self._logger = get_logger("persistence")
        
        # Ensure base path exists
        os.makedirs(base_path, exist_ok=True)

    def _get_snapshot_path(self, name: str) -> str:
        """Get the full path for a snapshot file, preventing path traversal."""
        safe_name = os.path.basename(name)
        if not safe_name or safe_name != name or ".." in name or "/" in name or "\\" in name:
            raise PersistenceError(
                f"Invalid snapshot name: {name}",
                reason="Path traversal or invalid characters detected",
            )
        return os.path.join(self._base_path, f"{safe_name}.snapshot")

    def _get_temp_path(self, name: str) -> str:
        """Get the temporary file path for atomic writes."""
        safe_name = os.path.basename(name)
        return os.path.join(self._base_path, f".{safe_name}.snapshot.tmp")

    def save(self, snapshot: Snapshot, name: str) -> str:
        """Save a snapshot atomically.
        
        Returns the path to the saved snapshot.
        """
        with self._lock:
            snapshot_path = self._get_snapshot_path(name)
            temp_path = self._get_temp_path(name)

            try:
                # Compute checksum if enabled
                if self._checksum_enabled:
                    snapshot.checksum = snapshot.compute_checksum()

                # Write to temporary file first
                data = snapshot.to_dict()
                
                # Write binary with header
                with open(temp_path, "wb") as f:
                    # Write magic header
                    f.write(MAGIC_HEADER)
                    # Write JSON data
                    json_bytes = json.dumps(data, indent=2).encode("utf-8")
                    f.write(json_bytes)

                # Atomic rename
                shutil.move(temp_path, snapshot_path)

                self._logger.info(f"Saved snapshot: {name} at tick {snapshot.tick}")
                return snapshot_path

            except Exception as e:
                # Clean up temp file on failure
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass
                raise PersistenceError(
                    f"Failed to save snapshot: {e}",
                    path=snapshot_path,
                    reason=str(e),
                )

    def load(self, name: str, verify_checksum: bool = True) -> Snapshot:
        """Load a snapshot and verify integrity.
        
        Args:
            name: Snapshot name
            verify_checksum: If True, verify the checksum
            
        Returns:
            The loaded Snapshot
            
        Raises:
            PersistenceError: If loading fails or integrity check fails
        """
        with self._lock:
            snapshot_path = self._get_snapshot_path(name)

            if not os.path.exists(snapshot_path):
                raise PersistenceError(
                    f"Snapshot not found: {name}",
                    path=snapshot_path,
                    reason="File not found",
                )

            try:
                with open(snapshot_path, "rb") as f:
                    # Verify magic header
                    header = f.read(len(MAGIC_HEADER))
                    if header != MAGIC_HEADER:
                        raise PersistenceError(
                            f"Invalid snapshot format: {name}",
                            path=snapshot_path,
                            reason="Invalid magic header",
                        )

                    # Read JSON data
                    json_data = f.read()
                    data = json.loads(json_data.decode("utf-8"))

                snapshot = Snapshot.from_dict(data)

                # Verify checksum if enabled
                if verify_checksum and self._checksum_enabled:
                    expected_checksum = snapshot.compute_checksum()
                    if snapshot.checksum != expected_checksum:
                        raise PersistenceError(
                            f"Checksum mismatch for snapshot: {name}",
                            path=snapshot_path,
                            reason=f"Expected {expected_checksum}, got {snapshot.checksum}",
                        )

                # Verify schema version
                if snapshot.schema_version != SCHEMA_VERSION:
                    self._logger.warning(
                        f"Schema version mismatch: expected {SCHEMA_VERSION}, "
                        f"got {snapshot.schema_version}"
                    )

                self._logger.info(f"Loaded snapshot: {name} from tick {snapshot.tick}")
                return snapshot

            except json.JSONDecodeError as e:
                raise PersistenceError(
                    f"Corrupted snapshot data: {name}",
                    path=snapshot_path,
                    reason=f"JSON decode error: {e}",
                )
            except PersistenceError:
                raise
            except Exception as e:
                raise PersistenceError(
                    f"Failed to load snapshot: {name}",
                    path=snapshot_path,
                    reason=str(e),
                )

    def exists(self, name: str) -> bool:
        """Check if a snapshot exists."""
        snapshot_path = self._get_snapshot_path(name)
        return os.path.exists(snapshot_path)

    def delete(self, name: str):
        """Delete a snapshot."""
        with self._lock:
            snapshot_path = self._get_snapshot_path(name)
            if os.path.exists(snapshot_path):
                os.remove(snapshot_path)
                self._logger.debug(f"Deleted snapshot: {name}")

    def list_snapshots(self) -> List[str]:
        """List all available snapshots."""
        snapshots = []
        for filename in os.listdir(self._base_path):
            if filename.endswith(".snapshot") and not filename.startswith("."):
                snapshots.append(filename[:-10])  # Remove .snapshot extension
        return sorted(snapshots)

    def get_latest_snapshot(self) -> Optional[str]:
        """Get the name of the most recent snapshot."""
        snapshots = self.list_snapshots()
        return snapshots[-1] if snapshots else None

    def verify_snapshot(self, name: str) -> bool:
        """Verify a snapshot's integrity without fully loading it.
        
        Returns True if the snapshot is valid, False otherwise.
        """
        try:
            snapshot_path = self._get_snapshot_path(name)
            if not os.path.exists(snapshot_path):
                return False

            with open(snapshot_path, "rb") as f:
                header = f.read(len(MAGIC_HEADER))
                if header != MAGIC_HEADER:
                    return False

                json_data = f.read()
                data = json.loads(json_data.decode("utf-8"))

            snapshot = Snapshot.from_dict(data)
            
            if self._checksum_enabled:
                expected = snapshot.compute_checksum()
                if snapshot.checksum != expected:
                    return False

            return True

        except Exception:
            return False

    def get_base_path(self) -> str:
        """Get the base path for snapshots."""
        return self._base_path
