"""ASTRA Scientific — migration helpers for legacy Provenance enums.

If ``astra/evolution/provenance.py`` previously defined its own
``Provenance`` (6 values) or ``astra/celestial/provenance.py`` defines
``DataProvenance`` (5 values), this module maps them to the canonical
``Classification``.  Phase 22's ``astra/evolution/provenance.py`` now
re-exports ``Classification`` directly, so this file is only needed for
external legacy data and tests.

The downstream agent must ensure there is exactly one enum definition
outside this package; legacy shims must be imports, not new classes.
"""

from __future__ import annotations

from .classification import Classification


_LEGACY_MAP = {
    # Evolution legacy (6-value) — direct 1:1
    "REAL_DATA": Classification.REAL_DATA,
    "DERIVED_DATA": Classification.DERIVED_DATA,
    "SIMULATED_DATA": Classification.SIMULATED_DATA,
    "THEORETICAL": Classification.THEORETICAL,
    "HYPOTHETICAL": Classification.HYPOTHETICAL,
    "SPECULATIVE": Classification.SPECULATIVE,
    # Celestial legacy (5-value) — THEORETICAL_MODEL → THEORETICAL, etc.
    "THEORETICAL_MODEL": Classification.THEORETICAL,
    "SPECULATIVE_MODEL": Classification.SPECULATIVE,
    # Alternative naming seen in some models
    "REAL_PHYSICS": Classification.THEORETICAL,
    "DERIVED_MODEL": Classification.DERIVED_DATA,
    "SIMULATION": Classification.SIMULATED_DATA,
}


def migrate_legacy(value: str | Classification | Enum) -> Classification:  # type: ignore[name-defined]
    """Map a legacy string or enum member to the canonical Classification.

    Accepts:
    - string names (e.g. "REAL_DATA", "THEORETICAL_MODEL")
    - enum members from DataProvenance or legacy Provenance (via .value or .name)
    - already-canonical Classification members (returned as-is)
    """
    # Pass-through canonical
    if isinstance(value, Classification):
        return value
    # Enum-like (DataProvenance, legacy Provenance)
    if hasattr(value, "value") and isinstance(value.value, str):
        key = str(value.value)
        if key in _LEGACY_MAP:
            return _LEGACY_MAP[key]
        # Try name fallback
        key2 = str(getattr(value, "name", ""))
        if key2 in _LEGACY_MAP:
            return _LEGACY_MAP[key2]
        raise ValueError(f"unknown legacy provenance value: {value!r} (value={key!r})")
    if hasattr(value, "name") and isinstance(value.name, str):
        key = str(value.name)
        if key in _LEGACY_MAP:
            return _LEGACY_MAP[key]
    if isinstance(value, str):
        if value in _LEGACY_MAP:
            return _LEGACY_MAP[value]
        raise ValueError(f"unknown legacy provenance value: {value!r}")
    raise TypeError(f"cannot migrate {value!r} to Classification")


def is_canonical(obj) -> bool:
    """True if ``obj`` is already a canonical Classification member."""
    return isinstance(obj, Classification)


# For typing convenience, Enum import is optional
try:
    from enum import Enum  # noqa: F401
except ImportError:
    pass
