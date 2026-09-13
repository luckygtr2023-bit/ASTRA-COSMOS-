"""ASTRA Core ID types for deterministic identification."""

import uuid
from dataclasses import dataclass, field
from typing import NewType


@dataclass(frozen=True)
class EntityId:
    """Deterministic entity identifier."""

    value: str

    @classmethod
    def generate(cls, tick: int, sequence: int) -> "EntityId":
        """Generate a deterministic ID based on tick and sequence."""
        return cls(f"entity_{tick:012d}_{sequence:06d}")

    @classmethod
    def random(cls) -> "EntityId":
        """Generate a random ID (for non-deterministic contexts only)."""
        return cls(f"entity_{uuid.uuid4().hex}")


@dataclass(frozen=True)
class CommandId:
    """Deterministic command identifier."""

    value: str

    @classmethod
    def generate(cls, tick: int, sequence: int) -> "CommandId":
        """Generate a deterministic ID based on tick and sequence."""
        return cls(f"cmd_{tick:012d}_{sequence:06d}")

    @classmethod
    def random(cls) -> "CommandId":
        """Generate a random ID."""
        return cls(f"cmd_{uuid.uuid4().hex}")


@dataclass(frozen=True)
class EventId:
    """Deterministic event identifier."""

    value: str

    @classmethod
    def generate(cls, tick: int, sequence: int) -> "EventId":
        """Generate a deterministic ID based on tick and sequence."""
        return cls(f"evt_{tick:012d}_{sequence:06d}")

    @classmethod
    def random(cls) -> "EventId":
        """Generate a random ID."""
        return cls(f"evt_{uuid.uuid4().hex}")


@dataclass(frozen=True)
class FrameId:
    """Coordinate frame identifier."""

    value: str

    @classmethod
    def from_name(cls, name: str) -> "FrameId":
        """Create a frame ID from a name."""
        return cls(f"frame_{name}")

    @classmethod
    def random(cls) -> "FrameId":
        """Generate a random ID."""
        return cls(f"frame_{uuid.uuid4().hex}")


# Type aliases for convenience
TickId = NewType("TickId", int)
SequenceId = NewType("SequenceId", int)
