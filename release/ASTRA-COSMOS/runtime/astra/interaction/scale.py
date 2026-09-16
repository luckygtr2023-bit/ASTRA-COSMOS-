"""ASTRA Interaction — multi-scale navigation levels.

Hierarchical scales mirror the spec (§8):
  LOCAL_ENVIRONMENT → PLANETARY_SYSTEM → STELLAR_SYSTEM → GALACTIC_REGION → GALAXY
  → GALAXY_GROUP → CLUSTER → SUPERCLUSTER → COSMIC_WEB → LARGE_SCALE_UNIVERSE

No new coordinate system is introduced; scales are labels for navigation
that map to existing World/Frame hierarchies.
"""

from __future__ import annotations

from enum import Enum


class ScaleLevel(str, Enum):
    LOCAL_ENVIRONMENT = "LOCAL_ENVIRONMENT"
    PLANETARY_SYSTEM = "PLANETARY_SYSTEM"
    STELLAR_SYSTEM = "STELLAR_SYSTEM"
    GALACTIC_REGION = "GALACTIC_REGION"
    GALAXY = "GALAXY"
    GALAXY_GROUP = "GALAXY_GROUP"
    CLUSTER = "CLUSTER"
    SUPERCLUSTER = "SUPERCLUSTER"
    COSMIC_WEB = "COSMIC_WEB"
    LARGE_SCALE_UNIVERSE = "LARGE_SCALE_UNIVERSE"


# Ordered list for deterministic comparisons
_SCALE_ORDER = [
    ScaleLevel.LOCAL_ENVIRONMENT,
    ScaleLevel.PLANETARY_SYSTEM,
    ScaleLevel.STELLAR_SYSTEM,
    ScaleLevel.GALACTIC_REGION,
    ScaleLevel.GALAXY,
    ScaleLevel.GALAXY_GROUP,
    ScaleLevel.CLUSTER,
    ScaleLevel.SUPERCLUSTER,
    ScaleLevel.COSMIC_WEB,
    ScaleLevel.LARGE_SCALE_UNIVERSE,
]

_ORDER_MAP = {s: i for i, s in enumerate(_SCALE_ORDER)}


def scale_order(s: ScaleLevel) -> int:
    return _ORDER_MAP[s]


def is_coarser(a: ScaleLevel, b: ScaleLevel) -> bool:
    """True if a is coarser (larger) than b."""
    return _ORDER_MAP[a] > _ORDER_MAP[b]


def is_finer(a: ScaleLevel, b: ScaleLevel) -> bool:
    return _ORDER_MAP[a] < _ORDER_MAP[b]


def scale_transition_steps(from_scale: ScaleLevel, to_scale: ScaleLevel) -> int:
    return abs(_ORDER_MAP[to_scale] - _ORDER_MAP[from_scale])


def all_scales() -> tuple[ScaleLevel, ...]:
    return tuple(_SCALE_ORDER)
