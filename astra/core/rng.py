"""ASTRA Core deterministic random number generation."""

import random
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Tuple, Any
from copy import deepcopy

from astra.core.logging import get_logger


@dataclass
class RNGState:
    """Snapshot of RNG state for deterministic replay.
    
    Uses Python's native getstate()/setstate() mechanism for reliable
    state capture and restoration across all RNG methods.
    """
    
    seed: int
    internal_state: Any  # The opaque state tuple from random.Random.getstate()


class RNGStream:
    """Isolated deterministic random number stream.
    
    Uses Python's random.Random with explicit state management via
    getstate()/setstate() for reliable snapshot/restore regardless
    of which methods (random, randint, choice, etc.) are called.
    """

    def __init__(self, name: str, seed: int):
        self.name = name
        self._seed = seed
        self._rng = random.Random(seed)
        self._lock = threading.Lock()
        self._logger = get_logger(f"rng.{name}")

    def next_int(self, min_val: int = 0, max_val: int = 2**31 - 1) -> int:
        """Generate a random integer in [min_val, max_val]."""
        with self._lock:
            return self._rng.randint(min_val, max_val)

    def next_float(self) -> float:
        """Generate a random float in [0.0, 1.0)."""
        with self._lock:
            return self._rng.random()

    def next_gauss(self, mu: float = 0.0, sigma: float = 1.0) -> float:
        """Generate a Gaussian random value."""
        with self._lock:
            return self._rng.gauss(mu, sigma)

    def choice(self, seq: list):
        """Choose a random element from a sequence."""
        with self._lock:
            return self._rng.choice(seq)

    def shuffle(self, seq: list) -> list:
        """Shuffle a sequence (returns a new shuffled list)."""
        with self._lock:
            result = seq.copy()
            self._rng.shuffle(result)
            return result

    def randint(self, a: int, b: int) -> int:
        """Generate a random integer between a and b (inclusive)."""
        with self._lock:
            return self._rng.randint(a, b)

    def randrange(self, start: int, stop: int = None, step: int = 1) -> int:
        """Generate a random integer from range(start, stop[, step])."""
        with self._lock:
            if stop is None:
                return self._rng.randrange(start)
            return self._rng.randrange(start, stop, step)

    def uniform(self, a: float, b: float) -> float:
        """Generate a random float between a and b."""
        with self._lock:
            return self._rng.uniform(a, b)

    def getrandbits(self, k: int) -> int:
        """Generate a random integer with k random bits."""
        with self._lock:
            return self._rng.getrandbits(k)

    def get_state(self) -> RNGState:
        """Get current state snapshot using Python's native state mechanism.
        
        This captures the exact internal state of the PRNG, ensuring that
        restore_state() will reproduce identical sequences regardless of
        which methods were used to consume state.
        """
        # Get the full internal state tuple from Python's random module
        internal_state = self._rng.getstate()
        return RNGState(
            seed=self._seed,
            internal_state=internal_state,
        )

    def restore_state(self, state: RNGState):
        """Restore from a state snapshot using Python's native state mechanism.
        
        This restores the exact internal state, ensuring subsequent calls
        produce identical results to the original execution.
        """
        if state.seed != self._seed:
            raise ValueError(
                f"Cannot restore state: seed mismatch ({state.seed} != {self._seed})"
            )
        # Use Python's setstate to restore the exact internal state
        self._rng.setstate(state.internal_state)
        self._logger.debug(f"RNG stream '{self.name}' restored to saved state")

    def reset(self):
        """Reset the stream to its initial state."""
        self._rng = random.Random(self._seed)
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
