"""ASTRA Core deterministic random number generation."""

import random
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Tuple
from copy import deepcopy

from astra.core.logging import get_logger


@dataclass
class RNGState:
    """Snapshot of RNG state for deterministic replay."""

    seed: int
    position: int
    values_consumed: int


class RNGStream:
    """Isolated deterministic random number stream."""

    def __init__(self, name: str, seed: int):
        self.name = name
        self._seed = seed
        self._rng = random.Random(seed)
        self._values_consumed = 0
        self._lock = threading.Lock()
        self._logger = get_logger(f"rng.{name}")

    def next_int(self, min_val: int = 0, max_val: int = 2**31 - 1) -> int:
        """Generate a random integer in [min_val, max_val]."""
        with self._lock:
            value = self._rng.randint(min_val, max_val)
            self._values_consumed += 1
            return value

    def next_float(self) -> float:
        """Generate a random float in [0.0, 1.0)."""
        with self._lock:
            value = self._rng.random()
            self._values_consumed += 1
            return value

    def next_gauss(self, mu: float = 0.0, sigma: float = 1.0) -> float:
        """Generate a Gaussian random value."""
        with self._lock:
            value = self._rng.gauss(mu, sigma)
            self._values_consumed += 1
            return value

    def choice(self, seq: list):
        """Choose a random element from a sequence."""
        with self._lock:
            value = self._rng.choice(seq)
            self._values_consumed += 1
            return value

    def shuffle(self, seq: list) -> list:
        """Shuffle a sequence (returns a new shuffled list)."""
        with self._lock:
            result = seq.copy()
            self._rng.shuffle(result)
            self._values_consumed += 1
            return result

    def get_state(self) -> RNGState:
        """Get current state snapshot."""
        # Get the internal state tuple
        internal_state = self._rng.getstate()
        # Position is the second element of the state tuple
        position = internal_state[1] if len(internal_state) > 1 else 0
        return RNGState(
            seed=self._seed,
            position=position,
            values_consumed=self._values_consumed,
        )

    def restore_state(self, state: RNGState):
        """Restore from a state snapshot."""
        if state.seed != self._seed:
            raise ValueError(
                f"Cannot restore state: seed mismatch ({state.seed} != {self._seed})"
            )
        # Re-seed and advance to the saved position
        self._rng = random.Random(self._seed)
        # Advance by consuming values
        for _ in range(state.values_consumed):
            self._rng.random()
        self._values_consumed = state.values_consumed

    def reset(self):
        """Reset the stream to its initial state."""
        self._rng = random.Random(self._seed)
        self._values_consumed = 0
        self._logger.debug(f"RNG stream '{self.name}' reset")


class DeterministicRNG:
    """Manager for isolated deterministic RNG streams."""

    def __init__(self, global_seed: int = 42):
        self._global_seed = global_seed
        self._streams: Dict[str, RNGStream] = {}
        self._stream_counter = 0
        self._lock = threading.Lock()
        self._logger = get_logger("rng")

    def create_stream(self, name: Optional[str] = None, seed: Optional[int] = None) -> RNGStream:
        """Create a new isolated RNG stream."""
        with self._lock:
            if name is None:
                self._stream_counter += 1
                name = f"stream_{self._stream_counter}"

            if name in self._streams:
                raise ValueError(f"RNG stream '{name}' already exists")

            # Derive seed deterministically if not provided
            if seed is None:
                # Use a master RNG to derive seeds
                master = random.Random(self._global_seed)
                # Advance based on stream counter to ensure unique seeds
                for _ in range(self._stream_counter * 7):
                    master.random()
                seed = master.randint(0, 2**31 - 1)

            stream = RNGStream(name, seed)
            self._streams[name] = stream
            self._logger.debug(f"Created RNG stream '{name}' with seed {seed}")
            return stream

    def get_stream(self, name: str) -> Optional[RNGStream]:
        """Get an existing stream by name."""
        return self._streams.get(name)

    def remove_stream(self, name: str):
        """Remove a stream."""
        with self._lock:
            if name in self._streams:
                del self._streams[name]
                self._logger.debug(f"Removed RNG stream '{name}'")

    def get_all_streams(self) -> Dict[str, RNGStream]:
        """Get all streams (read-only view)."""
        return dict(self._streams)

    def get_state(self) -> Dict[str, RNGState]:
        """Get state snapshots of all streams."""
        return {name: stream.get_state() for name, stream in self._streams.items()}

    def restore_state(self, states: Dict[str, RNGState]):
        """Restore all streams from state snapshots."""
        for name, state in states.items():
            stream = self._streams.get(name)
            if stream:
                stream.restore_state(state)

    def reset_all(self):
        """Reset all streams to their initial states."""
        for stream in self._streams.values():
            stream.reset()

    def set_global_seed(self, seed: int):
        """Set the global seed (affects future streams only)."""
        self._global_seed = seed
        self._logger.info(f"Global RNG seed set to {seed}")
