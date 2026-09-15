"""ASTRA-COSMOS Verification & Validation subsystem.

Deterministic replay, canonical state hashing, comparison, snapshot verification,
numerical invariants, world/celestial checks, stress/corruption detection,
reports and fixtures.

Bounds documented per module; verification never fabricates authoritative data
and never excludes semantic state from hashes (excludes only wall-clock metadata).
"""

from __future__ import annotations

from .state_hash import (
    canonical_json,
    hash_snapshot,
    hash_engine,
    hash_world,
    hash_render_state,
    hash_canonical,
)
from .state_compare import compare_snapshots, compare_canonical, assert_snapshots_equal
from .snapshot import (
    verify_save_load_equivalence,
    verify_save_load_continue_equivalence,
    detect_corrupted_snapshot,
)
from .replay import (
    ReplayRecord,
    ReplayRecorder,
    ReplayVerifier,
    verify_deterministic_replay,
)
from .numerical import (
    is_close,
    vectors_close,
    verify_energy_conservation,
    verify_orbital_stability,
)
from .invariants import (
    check_mass_positive,
    check_orbital_elements,
    collect_physics_invariants,
)
from .world_checks import collect_world_checks
from .celestial_checks import collect_celestial_checks
from .stress import (
    stress_long_run,
    stress_save_load_cycles,
    verify_corruption_detection,
)
from .report import VerificationReport, build_report
from .fixtures import engine_factory, minimal_world_factory
from .integration import full_integration_report
from .exceptions import (
    VerificationError,
    HashError,
    ComparisonError,
    SnapshotVerificationError,
    ReplayDivergenceError,
    InvariantViolationError,
    CorruptedStateError,
)

__all__ = [
    "canonical_json",
    "hash_snapshot",
    "hash_engine",
    "hash_world",
    "hash_render_state",
    "hash_canonical",
    "compare_snapshots",
    "compare_canonical",
    "assert_snapshots_equal",
    "verify_save_load_equivalence",
    "verify_save_load_continue_equivalence",
    "detect_corrupted_snapshot",
    "ReplayRecord",
    "ReplayRecorder",
    "ReplayVerifier",
    "verify_deterministic_replay",
    "is_close",
    "vectors_close",
    "verify_energy_conservation",
    "verify_orbital_stability",
    "check_mass_positive",
    "check_orbital_elements",
    "collect_physics_invariants",
    "collect_world_checks",
    "collect_celestial_checks",
    "stress_long_run",
    "stress_save_load_cycles",
    "verify_corruption_detection",
    "VerificationReport",
    "build_report",
    "engine_factory",
    "minimal_world_factory",
    "full_integration_report",
    "VerificationError",
    "HashError",
    "ComparisonError",
    "SnapshotVerificationError",
    "ReplayDivergenceError",
    "InvariantViolationError",
    "CorruptedStateError",
]

__version__ = "1.0.0"
