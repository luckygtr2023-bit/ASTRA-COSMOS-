"""ASTRA Rendering - spacetime / black-hole / wormhole / warp rendering interfaces.

These are data containers that consume outputs from:
- astra.relativity
- astra.blackhole
- astra.spacetime
- astra.theoretical (wormhole / warp)

They expose derived visual parameters (horizon radii, photon spheres,
lensing hints, distortion) without duplicating physics or building full VFX.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from astra.mathematics import Vector3

from astra.rendering.exceptions import SpacetimeRenderError
from astra.rendering.render_state import RenderObject, MaterialRef
from astra.rendering.types import RenderObjectKind


def _finite(name: str, v, low=None, high=None) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise SpacetimeRenderError(f"{name} must be numeric, got {type(v).__name__}")
    f = float(v)
    if math.isnan(f) or math.isinf(f):
        raise SpacetimeRenderError(f"{name} must be finite, got {v!r}")
    if low is not None and f < low:
        raise SpacetimeRenderError(f"{name} must be >= {low}, got {f}")
    if high is not None and f > high:
        raise SpacetimeRenderError(f"{name} must be <= {high}, got {f}")
    return f


def _require_vector(v: Vector3, name: str) -> Vector3:
    if not isinstance(v, Vector3):
        raise SpacetimeRenderError(f"{name} must be Vector3, got {type(v).__name__}")
    if not v.is_finite():
        raise SpacetimeRenderError(f"{name} must be finite, got {v!r}")
    return v


# ---------------------------------------------------------------------------
# Black-hole rendering
# ---------------------------------------------------------------------------

@dataclass
class BlackHoleRenderParams:
    """Renderer-independent black-hole visual parameters (derived, not computed here beyond delegation)."""

    object_id: str
    mass_kg: float
    spin_param: float  # -1..1
    # geometric boundaries (meters), derived from astra.blackhole
    schwarzschild_radius_m: float
    photon_sphere_radius_m: Optional[float] = None
    isco_radius_m: Optional[float] = None
    # Kerr specifics (if spinning)
    horizon_outer_m: Optional[float] = None
    horizon_inner_m: Optional[float] = None
    ergosphere_equatorial_m: Optional[float] = None
    # visual hints
    lensing_strength: float = 1.0  # 0.. ~5 (normalized for shader)
    redshift_hint: float = 0.0  # dimensionless preview
    accretion_disk_hint: Optional[Dict[str, Any]] = None  # placeholder for future VFX
    material: MaterialRef = field(default_factory=lambda: MaterialRef(id="black_hole_horizon", kind="black_hole_placeholder"))

    def __post_init__(self) -> None:
        if not isinstance(self.object_id, str) or not self.object_id:
            raise SpacetimeRenderError("object_id must be non-empty string")
        self.mass_kg = _finite("mass_kg", self.mass_kg, low=1e-9)
        self.spin_param = _finite("spin_param", self.spin_param, low=-1.0, high=1.0)
        self.schwarzschild_radius_m = _finite("schwarzschild_radius_m", self.schwarzschild_radius_m, low=1e-9)
        if self.photon_sphere_radius_m is not None:
            self.photon_sphere_radius_m = _finite("photon_sphere_radius_m", self.photon_sphere_radius_m, low=1e-9)
        if self.isco_radius_m is not None:
            self.isco_radius_m = _finite("isco_radius_m", self.isco_radius_m, low=1e-9)
        self.lensing_strength = _finite("lensing_strength", self.lensing_strength, low=0.0, high=10.0)

    def to_render_object(
        self,
        world_position: Vector3,
        render_origin: Optional[Vector3] = None,
    ) -> RenderObject:
        _require_vector(world_position, "world_position")
        render_pos = world_position - render_origin if render_origin is not None else Vector3(world_position.x, world_position.y, world_position.z)
        # Bounding radius: use photon sphere if available else Schwarzschild radius * 1.5
        radius = self.photon_sphere_radius_m or (self.schwarzschild_radius_m * 1.5)
        return RenderObject(
            id=f"bh_{self.object_id}",
            name=f"BlackHole {self.object_id}",
            kind=RenderObjectKind.BLACK_HOLE,
            category="BLACK_HOLE",
            position=render_pos,
            bounding_radius_m=float(radius),
            material=self.material,
            emissive=False,
            casts_shadow=False,
            receives_light=False,
            metadata={
                "mass_kg": self.mass_kg,
                "spin_param": self.spin_param,
                "rs_m": self.schwarzschild_radius_m,
                "photon_sphere_m": self.photon_sphere_radius_m,
                "isco_m": self.isco_radius_m,
                "lensing_strength": self.lensing_strength,
                "accretion": self.accretion_disk_hint,
            },
            source_ref=self.object_id,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "object_id": self.object_id,
            "mass_kg": self.mass_kg,
            "spin_param": self.spin_param,
            "schwarzschild_radius_m": self.schwarzschild_radius_m,
            "photon_sphere_radius_m": self.photon_sphere_radius_m,
            "isco_radius_m": self.isco_radius_m,
            "horizon_outer_m": self.horizon_outer_m,
            "ergosphere_equatorial_m": self.ergosphere_equatorial_m,
            "lensing_strength": self.lensing_strength,
        }


def black_hole_state_to_render_params(bh_state, object_id: str = "bh") -> BlackHoleRenderParams:
    """Convert an authoritative BlackHoleState to visual params.

    Delegates geometry to astra.blackhole api (single implementation); no
    physics duplication.
    """
    from astra.blackhole.api import get_schwarzschild_boundaries, get_kerr_boundaries, calculate_ergosphere_radius  # type: ignore
    from astra.blackhole.models import BlackHoleModel  # type: ignore
    if bh_state is None or not hasattr(bh_state, "mass_kg") or not hasattr(bh_state, "spin_param"):
        raise SpacetimeRenderError(f"bh_state must be BlackHoleState, got {type(bh_state).__name__}")
    mass = float(bh_state.mass_kg)
    spin = float(bh_state.spin_param)
    # Get boundaries via facade
    try:
        if bh_state.model == BlackHoleModel.KERR:
            bounds = get_kerr_boundaries(bh_state)
            schwarz = get_schwarzschild_boundaries(bh_state)
            rs = schwarz["schwarzschild_radius"]
            return BlackHoleRenderParams(
                object_id=object_id,
                mass_kg=mass,
                spin_param=spin,
                schwarzschild_radius_m=float(rs),
                photon_sphere_radius_m=float(bounds.get("photon_orbit_prograde", rs*1.5)),
                isco_radius_m=float(bounds.get("isco_prograde", rs*3.0)),
                horizon_outer_m=float(bounds.get("r_plus", rs*0.5)),
                horizon_inner_m=float(bounds.get("r_minus", 0.0)),
                ergosphere_equatorial_m=float(bounds.get("ergosphere_equatorial", rs)),
                lensing_strength=min(5.0, max(0.5, math.log10(max(1.0, mass / 1e30)))),
            )
        else:
            bounds = get_schwarzschild_boundaries(bh_state)
            return BlackHoleRenderParams(
                object_id=object_id,
                mass_kg=mass,
                spin_param=spin,
                schwarzschild_radius_m=float(bounds["schwarzschild_radius"]),
                photon_sphere_radius_m=float(bounds["photon_sphere_radius"]),
                isco_radius_m=float(bounds["isco_radius"]),
                horizon_outer_m=float(bounds["schwarzschild_radius"]),
                lensing_strength=min(5.0, max(0.5, math.log10(max(1.0, mass / 1e30)))),
            )
    except Exception as e:
        raise SpacetimeRenderError(f"failed to derive black-hole render params: {e}") from e


@dataclass
class SpacetimeCurvatureVisual:
    """Placeholder for curvature-derived visual hints."""

    object_id: str
    position: Vector3
    kretschmann_scalar: Optional[float] = None  # derived invariant hint
    tidal_hint: Optional[Vector3] = None
    curvature_strength: float = 0.0  # 0..1 normalized for VFX

    def __post_init__(self) -> None:
        _require_vector(self.position, "position")
        self.curvature_strength = _finite("curvature_strength", self.curvature_strength, low=0.0, high=1.0)
        if self.kretschmann_scalar is not None:
            _finite("kretschmann_scalar", self.kretschmann_scalar)


# ---------------------------------------------------------------------------
# Wormhole / Warp
# ---------------------------------------------------------------------------

@dataclass
class WormholeRenderParams:
    """Renderer-independent wormhole visual."""

    object_id: str
    throat_radius_m: float
    shape_hint: str = "morris_thorne"
    classification: str = "SPECULATIVE"
    lensing_strength: float = 1.0
    throat_position: Vector3 = field(default_factory=lambda: Vector3(0.0, 0.0, 0.0))
    mouth_radius_m: Optional[float] = None
    embedding_hint: Optional[Dict[str, Any]] = None  # for future VFX
    material: MaterialRef = field(default_factory=lambda: MaterialRef(id="wormhole_throat", kind="wormhole_placeholder"))

    def __post_init__(self) -> None:
        if not isinstance(self.object_id, str) or not self.object_id:
            raise SpacetimeRenderError("object_id must be non-empty string")
        self.throat_radius_m = _finite("throat_radius_m", self.throat_radius_m, low=1e-9)
        self.lensing_strength = _finite("lensing_strength", self.lensing_strength, low=0.0, high=10.0)
        _require_vector(self.throat_position, "throat_position")
        if self.mouth_radius_m is not None:
            self.mouth_radius_m = _finite("mouth_radius_m", self.mouth_radius_m, low=1e-9)

    def to_render_object(self, render_origin: Optional[Vector3] = None) -> RenderObject:
        pos = self.throat_position - render_origin if render_origin is not None else Vector3(self.throat_position.x, self.throat_position.y, self.throat_position.z)
        return RenderObject(
            id=f"wormhole_{self.object_id}",
            name=f"Wormhole {self.object_id}",
            kind=RenderObjectKind.WORMHOLE,
            category="WORMHOLE",
            position=pos,
            bounding_radius_m=float(self.throat_radius_m * 2.0),
            material=self.material,
            emissive=False,
            metadata={
                "throat_radius_m": self.throat_radius_m,
                "shape_hint": self.shape_hint,
                "classification": self.classification,
                "lensing_strength": self.lensing_strength,
                "mouth_radius_m": self.mouth_radius_m,
            },
            source_ref=self.object_id,
        )


def wormhole_metric_to_render_params(metric, object_id: str = "wormhole") -> WormholeRenderParams:
    """Consume a theoretical wormhole metric (MorrisThorne / EinsteinRosen) to visual params."""
    # Duck-type: look for throat_radius_m or mass_kg
    try:
        if hasattr(metric, "throat_radius_m"):
            r0 = float(metric.throat_radius_m)  # MorrisThorne
            cls_val = getattr(metric, "classification", "SPECULATIVE")
            try:
                cls_str = cls_val.value if hasattr(cls_val, "value") else str(cls_val)
            except Exception:
                cls_str = "SPECULATIVE"
            # Normalize to plain string without enum prefix
            if "." in cls_str:
                cls_str = cls_str.split(".")[-1]
            return WormholeRenderParams(
                object_id=object_id,
                throat_radius_m=r0,
                shape_hint="morris_thorne",
                classification=cls_str,
                lensing_strength=1.5,
                throat_position=Vector3(0.0, 0.0, 0.0),
                mouth_radius_m=r0 * 1.5,
            )
        elif hasattr(metric, "mass_kg"):
            # EinsteinRosen - throat is ~2GM/c^2
            from astra.relativity.core import SPEED_OF_LIGHT  # type: ignore
            from astra.physics.constants import GRAVITATIONAL_CONSTANT as G  # type: ignore
            mass = float(metric.mass_kg) if hasattr(metric, "mass_kg") else float(getattr(metric, "_schw_mass")()) if callable(getattr(metric, "_schw_mass", None)) else 1e30
            rs = 2.0 * G * mass / (SPEED_OF_LIGHT ** 2)
            return WormholeRenderParams(
                object_id=object_id,
                throat_radius_m=float(rs),
                shape_hint="einstein_rosen",
                classification="THEORETICAL",
                lensing_strength=1.0,
                throat_position=Vector3(0.0, 0.0, 0.0),
                mouth_radius_m=float(rs),
            )
        else:
            raise SpacetimeRenderError(f"unrecognized wormhole metric type: {type(metric).__name__}")
    except SpacetimeRenderError:
        raise
    except Exception as e:
        raise SpacetimeRenderError(f"wormhole metric to render failed: {e}") from e


@dataclass
class WarpRenderParams:
    """Renderer-independent warp bubble visual."""

    object_id: str
    bubble_radius_m: float
    wall_steepness: float = 5.0
    velocity_m_s: float = 0.0
    shift_vector: Vector3 = field(default_factory=lambda: Vector3(1.0, 0.0, 0.0))
    distortion_strength: float = 1.0
    classification: str = "SPECULATIVE"
    material: MaterialRef = field(default_factory=lambda: MaterialRef(id="warp_bubble", kind="warp_placeholder"))

    def __post_init__(self) -> None:
        if not isinstance(self.object_id, str) or not self.object_id:
            raise SpacetimeRenderError("object_id must be non-empty string")
        self.bubble_radius_m = _finite("bubble_radius_m", self.bubble_radius_m, low=1.0)
        self.wall_steepness = _finite("wall_steepness", self.wall_steepness, low=0.1, high=100.0)
        self.velocity_m_s = _finite("velocity_m_s", self.velocity_m_s, low=0.0, high=3e8)
        _require_vector(self.shift_vector, "shift_vector")
        self.distortion_strength = _finite("distortion_strength", self.distortion_strength, low=0.0, high=10.0)

    def to_render_object(self, center: Vector3, render_origin: Optional[Vector3] = None) -> RenderObject:
        _require_vector(center, "center")
        pos = center - render_origin if render_origin is not None else Vector3(center.x, center.y, center.z)
        return RenderObject(
            id=f"warp_{self.object_id}",
            name=f"Warp {self.object_id}",
            kind=RenderObjectKind.WARP_BUBBLE,
            category="WARP_BUBBLE",
            position=pos,
            bounding_radius_m=float(self.bubble_radius_m),
            material=self.material,
            emissive=False,
            metadata={
                "bubble_radius_m": self.bubble_radius_m,
                "wall_steepness": self.wall_steepness,
                "velocity_m_s": self.velocity_m_s,
                "distortion_strength": self.distortion_strength,
                "classification": self.classification,
            },
            source_ref=self.object_id,
        )


def warp_metric_to_render_params(metric, object_id: str = "warp") -> WarpRenderParams:
    """Consume an AlcubierreMetric to visual params (fixed backgrounds, no backreaction)."""
    try:
        # AlcubierreMetric stores velocity, radius_m, wall_steepness
        radius = 100.0
        for attr in ("bubble_radius_m", "radius_m", "radius"):
            if hasattr(metric, attr):
                try:
                    radius = float(getattr(metric, attr))
                    break
                except Exception:
                    continue
        steep = 5.0
        for attr in ("wall_steepness", "sigma"):
            if hasattr(metric, attr):
                try:
                    steep = float(getattr(metric, attr))
                    break
                except Exception:
                    continue
        # velocity: may be stored as velocity, velocity_m_s, vs, v
        vel = 0.0
        for attr in ("velocity_m_s", "velocity", "vs", "v"):
            if hasattr(metric, attr):
                try:
                    vraw = getattr(metric, attr)
                    # if it's a property returning float, else callable
                    if callable(vraw):
                        vraw = vraw()
                    vel = float(vraw)
                    break
                except Exception:
                    continue
        shift = getattr(metric, "shift_vector", Vector3(1.0, 0.0, 0.0))
        if not isinstance(shift, Vector3):
            shift = Vector3(1.0, 0.0, 0.0)
        # classification may be an enum
        cls_val = getattr(metric, "classification", "SPECULATIVE")
        try:
            cls_str = cls_val.value if hasattr(cls_val, "value") else str(cls_val)
        except Exception:
            cls_str = "SPECULATIVE"
        return WarpRenderParams(
            object_id=object_id,
            bubble_radius_m=float(radius),
            wall_steepness=float(steep),
            velocity_m_s=float(vel),
            shift_vector=shift,
            distortion_strength=min(5.0, max(0.2, abs(vel) / 1e7)) if vel != 0 else 0.5,
            classification=cls_str,
        )
    except SpacetimeRenderError:
        raise
    except Exception as e:
        raise SpacetimeRenderError(f"warp metric to render failed: {e}") from e
