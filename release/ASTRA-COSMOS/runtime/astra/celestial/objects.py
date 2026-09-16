"""ASTRA Celestial - domain object definitions.

Contract: celestial objects are DEFINITIONS (immutable), not state
machines. A Star defines identity, taxonomy, and properties; its current
spatial state belongs to astra.motion, its history to astra.temporal, and
its dynamics to astra.nbody. Nothing here computes physics: the only
delegated calculation is BlackHoleObject's geometry, which is initialized
from the validated astra.blackhole layer (single implementation).

All specializations are frozen dataclasses; mass/radius accessors raise
IncompletePhysicalDataError on unknown data (never fabricate).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from astra.celestial.classification import LuminosityClass, ObjectCategory, SpectralType
from astra.celestial.exceptions import IncompletePhysicalDataError, InvalidPropertyError
from astra.celestial.identity import CelestialIdentity
from astra.celestial.properties import CelestialProperties


@dataclass(frozen=True)
class CelestialObject:
    """Base definition: identity + taxonomy + property block."""

    identity: CelestialIdentity
    properties: CelestialProperties
    category: ObjectCategory

    def __post_init__(self):
        if not isinstance(self.identity, CelestialIdentity):
            raise TypeError("identity must be a CelestialIdentity")
        if not isinstance(self.properties, CelestialProperties):
            raise TypeError("properties must be a CelestialProperties")
        if not isinstance(self.category, ObjectCategory):
            raise TypeError("category must be an ObjectCategory")

    # -- physics-pipeline interface (astra.physics / astra.nbody feed) ------
    def get_mass_kg(self) -> float:
        return self.properties.require_mass_kg()

    def get_radius_m(self) -> float:
        return self.properties.require_radius_m()


@dataclass(frozen=True)
class Star(CelestialObject):
    """Main-sequence-or-evolved star definition (taxonomy + properties)."""

    spectral_type: SpectralType = SpectralType.UNKNOWN
    luminosity_class: LuminosityClass = LuminosityClass.DWARF

    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self.spectral_type, SpectralType):
            raise TypeError("spectral_type must be a SpectralType")
        if not isinstance(self.luminosity_class, LuminosityClass):
            raise TypeError("luminosity_class must be a LuminosityClass")


@dataclass(frozen=True)
class BinarySystem(CelestialObject):
    """Two-star system definition. Barycenter resolution remains in
    astra.nbody.barycenter; this is the catalog-level definition."""

    companion: Optional[CelestialIdentity] = None


@dataclass(frozen=True)
class WhiteDwarf(CelestialObject):
    """Degenerate stellar remnant definition."""


@dataclass(frozen=True)
class NeutronStar(CelestialObject):
    """Neutron-star definition."""

    magnetic_field_tesla: Optional[float] = None

    def __post_init__(self):
        super().__post_init__()
        if self.magnetic_field_tesla is not None:
            b = float(self.magnetic_field_tesla)
            if b != b or b in (float("inf"),) or b < 0.0:
                raise InvalidPropertyError(
                    f"magnetic_field_tesla must be finite >= 0, got "
                    f"{self.magnetic_field_tesla!r}"
                )


@dataclass(frozen=True)
class Pulsar(NeutronStar):
    """Pulsar definition: rotation must be strictly positive (a 0 s pulse
    period is not an unknown, it is impossible)."""

    pulse_period_s: Optional[float] = None

    def __post_init__(self):
        super().__post_init__()
        if self.pulse_period_s is not None:
            import math
            p = float(self.pulse_period_s)
            if math.isnan(p) or math.isinf(p) or p <= 0.0:
                raise InvalidPropertyError(
                    f"pulse_period_s must be finite and > 0 when present, "
                    f"got {self.pulse_period_s!r}"
                )


@dataclass(frozen=True)
class Planet(CelestialObject):
    """Planet definition."""


@dataclass(frozen=True)
class DwarfPlanet(CelestialObject):
    """Dwarf-planet definition."""


@dataclass(frozen=True)
class Moon(CelestialObject):
    """Natural satellite definition (host link lives in the hierarchy)."""

    host_identity: Optional[CelestialIdentity] = None


@dataclass(frozen=True)
class Exoplanet(Planet):
    """Exoplanet definition (catalog aliases carry host-star designations)."""


@dataclass(frozen=True)
class Asteroid(CelestialObject):
    """Minor-planet definition."""


@dataclass(frozen=True)
class Comet(CelestialObject):
    """Comet definition (eccentricity/orbital elements live in astra.orbital)."""


@dataclass(frozen=True)
class Nebula(CelestialObject):
    """Nebula definition (mass, when known, is an order-of-magnitude
    catalog value; dust/gas dynamics are out of scope here)."""


@dataclass(frozen=True)
class Galaxy(CelestialObject):
    """Galaxy definition."""


@dataclass(frozen=True)
class StarCluster(CelestialObject):
    """Cluster definition (member identities live in the hierarchy DAG)."""


@dataclass(frozen=True)
class Quasar(CelestialObject):
    """Quasar definition."""


@dataclass(frozen=True)
class AGN(CelestialObject):
    """Active galactic nucleus definition."""


@dataclass(frozen=True)
class BlackHoleObject(CelestialObject):
    """Black-hole definition delegating geometry to astra.blackhole.

    The validated BlackHoleState is constructed from THIS object's mass
    and spin, so all horizon/ergosphere mathematics has a single
    implementation; this class only carries the astronomical definition.
    """

    spin_param: float = 0.0

    def __post_init__(self):
        super().__post_init__()
        # Delegate validation to the blackhole layer by constructing the
        # state eagerly (mass positivity + |a*| <= 1 enforced there).
        self.get_black_hole_state()

    def get_black_hole_state(self):
        """Validated astra.blackhole.parameters.BlackHoleState for this
        definition (raises InvalidBlackHoleMassError /
        InvalidSpinParameterError through the blackhole layer)."""
        from astra.blackhole.parameters import BlackHoleState
        return BlackHoleState(
            mass_kg=self.properties.require_mass_kg(),
            spin_param=self.spin_param,
        )

    def schwarzschild_radius_m(self) -> float:
        """Event-horizon radius via the blackhole layer (delegation, not
        duplication)."""
        from astra.blackhole.schwarzschild import schwarzschild_radius_m
        return schwarzschild_radius_m(self.properties.require_mass_kg())

    def photon_sphere_radius_m(self) -> float:
        """Photon-sphere radius (1.5 r_s) via the blackhole layer."""
        from astra.blackhole.schwarzschild import photon_sphere_radius
        return photon_sphere_radius(self.properties.require_mass_kg())
