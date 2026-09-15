"""ASTRA Celestial - astronomical object typings.

Contract: categorical foundations only. No physical behavior lives here -
dynamics belong to Motion/N-Body, geometry to Black-Hole/Spacetime, and
temporal state to Temporal. This module is pure taxonomy.
"""

from __future__ import annotations

from enum import Enum


class ObjectCategory(Enum):
    """Top-level astronomical category (domain modeling only)."""

    STAR = "STAR"
    BINARY_SYSTEM = "BINARY_SYSTEM"
    WHITE_DWARF = "WHITE_DWARF"
    NEUTRON_STAR = "NEUTRON_STAR"
    PULSAR = "PULSAR"
    PLANET = "PLANET"
    DWARF_PLANET = "DWARF_PLANET"
    MOON = "MOON"
    EXOPLANET = "EXOPLANET"
    ASTEROID = "ASTEROID"
    COMET = "COMET"
    NEBULA = "NEBULA"
    GALAXY = "GALAXY"
    STAR_CLUSTER = "STAR_CLUSTER"
    QUASAR = "QUASAR"
    AGN = "AGN"
    BLACK_HOLE = "BLACK_HOLE"


class SpectralType(Enum):
    """Main stellar spectral classes (taxonomy only, no physics)."""

    O = "O"
    B = "B"
    A = "A"
    F = "F"
    G = "G"
    K = "K"
    M = "M"
    L = "L"
    T = "T"
    Y = "Y"
    UNKNOWN = "UNKNOWN"


class LuminosityClass(Enum):
    """Yerkes luminosity classes (taxonomy only)."""

    HYPERGIANT = "0"
    SUPERGIANT = "I"
    BRIGHT_GIANT = "II"
    GIANT = "III"
    SUBGIANT = "IV"
    DWARF = "V"          # main sequence
    SUBDWARF = "VI"
    WHITE_DWARF = "VII"


# Which categories are gravitationally dominant "primary" hosts for
# hierarchy purposes (documentation helper; no physics attached).
HOST_CATEGORIES = frozenset((
    ObjectCategory.STAR,
    ObjectCategory.BINARY_SYSTEM,
    ObjectCategory.NEUTRON_STAR,
    ObjectCategory.WHITE_DWARF,
    ObjectCategory.PULSAR,
    ObjectCategory.BLACK_HOLE,
    ObjectCategory.PLANET,
    ObjectCategory.DWARF_PLANET,
    ObjectCategory.GALAXY,
    ObjectCategory.STAR_CLUSTER,
))
