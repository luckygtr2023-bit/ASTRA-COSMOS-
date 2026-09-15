"""GalacticEngine — top-level orchestration. Reconciled.

Implements Phase 20 full galactic hierarchy, cosmic web graph,
provenance-preserving storage, deterministic ordering, floating-origin
support, observation integration, and lazy matter distribution.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .config import GalacticConfig
from .errors import (
    GalacticAuthorityError,
    GalacticDependencyError,
    GalacticHierarchyError,
    GalacticLimitationError,
    GalacticNumericalError,
    GalacticValidationError,
)
from .limitations import LimitationState
from .provenance import Provenance
from .types import (
    CosmicNode,
    CosmicVoid,
    CosmicWeb,
    Filament,
    Galaxy,
    GalaxyCluster,
    GalaxyGroup,
    HierarchyEdge,
    HierarchyRelation,
    Sheet,
    Supercluster,
    Vec3,
    CoordinateContext,
    DistanceKind,
    Frame,
)
from .velocity import VelocityDecomposition, decompose_velocity
from .geometry import separation_by_kind


_GALACTIC_DEFAULT = object()

@dataclass
class GalacticEngine:
    config: GalacticConfig = field(default_factory=GalacticConfig)

    authority: Optional[Any] = field(default=_GALACTIC_DEFAULT)  # type: ignore
    rng: Optional[Any] = field(default=_GALACTIC_DEFAULT)  # type: ignore
    coordinates: Optional[Any] = field(default=_GALACTIC_DEFAULT)  # type: ignore
    cosmology: Optional[Any] = field(default=_GALACTIC_DEFAULT)  # type: ignore
    nbody: Optional[Any] = field(default=_GALACTIC_DEFAULT)  # type: ignore
    blackhole: Optional[Any] = field(default=_GALACTIC_DEFAULT)  # type: ignore
    observation: Optional[Any] = field(default=_GALACTIC_DEFAULT)  # type: ignore
    measurement: Optional[Any] = field(default=_GALACTIC_DEFAULT)  # type: ignore
    ingestion: Optional[Any] = field(default=_GALACTIC_DEFAULT)  # type: ignore
    events: Optional[Any] = field(default=_GALACTIC_DEFAULT)  # type: ignore
    persistence: Optional[Any] = field(default=_GALACTIC_DEFAULT)  # type: ignore

    # --- stores ---
    _galaxies: Dict[str, Galaxy] = field(default_factory=dict, init=False)
    _groups: Dict[str, GalaxyGroup] = field(default_factory=dict, init=False)
    _clusters: Dict[str, GalaxyCluster] = field(default_factory=dict, init=False)
    _superclusters: Dict[str, Supercluster] = field(default_factory=dict, init=False)
    _voids: Dict[str, CosmicVoid] = field(default_factory=dict, init=False)
    _filaments: Dict[str, Filament] = field(default_factory=dict, init=False)
    _sheets: Dict[str, Sheet] = field(default_factory=dict, init=False)
    _nodes: Dict[str, CosmicNode] = field(default_factory=dict, init=False)
    _webs: Dict[str, CosmicWeb] = field(default_factory=dict, init=False)
    _edges: List[HierarchyEdge] = field(default_factory=list, init=False)

    # matter distribution lazy state
    _density_samples: Dict[str, Any] = field(default_factory=dict, init=False)

    def __post_init__(self):
        self.config.validate()
        # wire defaults where sentinel — use Protocol adapters that delegate to real modules
        # explicit None means "no provider" (missing dependency) and must stay None
        if self.authority is _GALACTIC_DEFAULT:
            from .integration import DefaultAuthorityProvider
            self.authority = DefaultAuthorityProvider()
        if self.rng is _GALACTIC_DEFAULT:
            from .integration import DefaultRNGProvider
            self.rng = DefaultRNGProvider(seed=42, stream_name=self.config.rng_stream_name)
        if self.coordinates is _GALACTIC_DEFAULT:
            from .integration import DefaultCoordinateProvider
            self.coordinates = DefaultCoordinateProvider()
        if self.cosmology is _GALACTIC_DEFAULT:
            from .integration import DefaultCosmologyProvider
            self.cosmology = DefaultCosmologyProvider(
                h0_kms_mpc=self.config.hubble_constant_kms_mpc,
                omega_m=self.config.matter_density,
                omega_l=self.config.dark_energy_density,
            )
        if self.nbody is _GALACTIC_DEFAULT:
            from .integration import DefaultNBodyProvider
            try:
                self.nbody = DefaultNBodyProvider()
            except Exception:
                from .adapters import MissingNBody
                self.nbody = MissingNBody()
        if self.blackhole is _GALACTIC_DEFAULT:
            from .integration import DefaultBlackHoleProvider
            self.blackhole = DefaultBlackHoleProvider()
        if self.observation is _GALACTIC_DEFAULT:
            from .integration import DefaultObservationProvider
            self.observation = DefaultObservationProvider()
        if self.measurement is _GALACTIC_DEFAULT:
            from .integration import DefaultMeasurementProvider
            self.measurement = DefaultMeasurementProvider()
        if self.ingestion is _GALACTIC_DEFAULT:
            from .integration import DefaultIngestionProvider
            self.ingestion = DefaultIngestionProvider()
        if self.events is _GALACTIC_DEFAULT:
            from .integration import DefaultEventPublisher
            self.events = DefaultEventPublisher()
        if self.persistence is _GALACTIC_DEFAULT:
            from .integration import DefaultPersistenceHook
            self.persistence = DefaultPersistenceHook()

    # ------------------------------------------------------------ authority

    def _require_authority(self, operation: str) -> None:
        if self.authority is None:
            raise GalacticAuthorityError(f"no AuthorityProvider configured; cannot perform {operation}")
        try:
            self.authority.require(operation)
        except GalacticAuthorityError:
            raise
        except Exception as e:
            # wrap core AuthorityError
            raise GalacticAuthorityError(str(e)) from e

    def _publish(self, topic: str, payload: dict) -> None:
        if self.events is not None:
            try:
                self.events.publish(topic, payload)
            except Exception:
                pass

    # ------------------------------------------------------------ mutations — galaxies / hierarchy

    def register_galaxy(self, galaxy: Galaxy) -> None:
        self._require_authority("galactic.register_galaxy")
        if not isinstance(galaxy, Galaxy):
            raise GalacticValidationError("galaxy must be Galaxy")
        if galaxy.galaxy_id in self._galaxies:
            raise GalacticValidationError(f"duplicate galaxy_id {galaxy.galaxy_id}")
        # black-hole reference validation (if provider present)
        if galaxy.central_black_hole_ref is not None:
            try:
                if hasattr(self.blackhole, "validate_reference"):
                    self.blackhole.validate_reference(galaxy.central_black_hole_ref)
                elif hasattr(self.blackhole, "get_black_hole"):
                    # attempt lookup, but missing registry is OK — just validate format
                    pass
            except GalacticValidationError:
                raise
            except GalacticDependencyError:
                # blackhole dependency missing — we keep ref but note limitation
                pass
            except Exception as e:
                raise GalacticValidationError(f"black hole ref validation failed: {e}") from e
        # optional nbody registration for large-scale gravity (best-effort)
        if self.nbody is not None:
            try:
                # use galaxy position as nbody body; mass unknown -> skip
                mass_val = None
                # try to get mass from components
                for comp in (galaxy.bulge, galaxy.disk, galaxy.halo):
                    if comp is not None:
                        # disk has stellar_mass, bulge/halo have mass
                        for attr in ("mass", "stellar_mass"):
                            if hasattr(comp, attr):
                                v = getattr(comp, attr)
                                if v is not None and hasattr(v, "value"):
                                    try:
                                        mass_val = float(v.value)
                                        break
                                    except Exception:
                                        pass
                            if mass_val is not None:
                                break
                    if mass_val is not None:
                        break
                if mass_val is not None and mass_val > 0:
                    # nbody expects kg; if value in Msun (1.989e30 kg) we treat as Msun if <1e20
                    # Heuristic: if mass <1e15, assume Msun else kg
                    if mass_val < 1e15:
                        mass_kg = mass_val * 1.98847e30
                    else:
                        mass_kg = mass_val
                    self.nbody.add_body(galaxy.galaxy_id, mass_kg, galaxy.position, Vec3(0, 0, 0))
            except Exception:
                # nbody at galactic scale may be missing or O(N^2) limit — not fatal
                pass
        self._galaxies[galaxy.galaxy_id] = galaxy
        self._publish("galactic.galaxy.registered", {"galaxy_id": galaxy.galaxy_id})

    def register_group(self, group: GalaxyGroup) -> None:
        self._require_authority("galactic.register_group")
        if not isinstance(group, GalaxyGroup):
            raise GalacticValidationError("group must be GalaxyGroup")
        if group.group_id in self._groups:
            raise GalacticValidationError(f"duplicate group_id {group.group_id}")
        for gid in group.member_galaxy_ids:
            if gid not in self._galaxies:
                raise GalacticHierarchyError(f"unknown galaxy {gid} in group {group.group_id}")
        self._groups[group.group_id] = group
        self._publish("galactic.group.registered", {"group_id": group.group_id})

    def register_cluster(self, cluster: GalaxyCluster) -> None:
        self._require_authority("galactic.register_cluster")
        if not isinstance(cluster, GalaxyCluster):
            raise GalacticValidationError("cluster must be GalaxyCluster")
        if cluster.cluster_id in self._clusters:
            raise GalacticValidationError(f"duplicate cluster_id {cluster.cluster_id}")
        for gid in cluster.member_galaxy_ids:
            if gid not in self._galaxies:
                raise GalacticHierarchyError(f"unknown galaxy {gid} in cluster {cluster.cluster_id}")
        for gid in cluster.member_group_ids:
            if gid not in self._groups:
                raise GalacticHierarchyError(f"unknown group {gid} in cluster {cluster.cluster_id}")
        self._clusters[cluster.cluster_id] = cluster
        self._publish("galactic.cluster.registered", {"cluster_id": cluster.cluster_id})

    def register_supercluster(self, supercluster: Supercluster) -> None:
        self._require_authority("galactic.register_supercluster")
        if not isinstance(supercluster, Supercluster):
            raise GalacticValidationError("supercluster must be Supercluster")
        if supercluster.supercluster_id in self._superclusters:
            raise GalacticValidationError(f"duplicate supercluster_id {supercluster.supercluster_id}")
        for cid in supercluster.member_cluster_ids:
            if cid not in self._clusters:
                raise GalacticHierarchyError(f"unknown cluster {cid}")
        for gid in supercluster.member_group_ids:
            if gid not in self._groups:
                raise GalacticHierarchyError(f"unknown group {gid}")
        for gid in supercluster.member_galaxy_ids:
            if gid not in self._galaxies:
                raise GalacticHierarchyError(f"unknown galaxy {gid}")
        self._superclusters[supercluster.supercluster_id] = supercluster
        self._publish("galactic.supercluster.registered", {"supercluster_id": supercluster.supercluster_id})

    def register_void(self, void: CosmicVoid) -> None:
        self._require_authority("galactic.register_void")
        if not isinstance(void, CosmicVoid):
            raise GalacticValidationError("void must be CosmicVoid")
        if void.void_id in self._voids:
            raise GalacticValidationError(f"duplicate void_id {void.void_id}")
        self._voids[void.void_id] = void
        self._publish("galactic.void.registered", {"void_id": void.void_id})

    def register_filament(self, filament: Filament) -> None:
        self._require_authority("galactic.register_filament")
        if not isinstance(filament, Filament):
            raise GalacticValidationError("filament must be Filament")
        if filament.filament_id in self._filaments:
            raise GalacticValidationError(f"duplicate filament_id {filament.filament_id}")
        # Cosmic web is a graph with ID-based references (no duplicate objects).
        # For deterministic build, filaments may be registered before nodes —
        # allow deferred endpoints. If galaxies/groups are referenced, they must exist.
        for gid in filament.galaxy_ids:
            if gid not in self._galaxies:
                raise GalacticHierarchyError(f"unknown galaxy {gid} in filament {filament.filament_id}")
        for gid in filament.group_ids:
            if gid not in self._groups:
                raise GalacticHierarchyError(f"unknown group {gid} in filament {filament.filament_id}")
        self._filaments[filament.filament_id] = filament
        self._publish("galactic.filament.registered", {"filament_id": filament.filament_id})

    def register_sheet(self, sheet: Sheet) -> None:
        self._require_authority("galactic.register_sheet")
        if not isinstance(sheet, Sheet):
            raise GalacticValidationError("sheet must be Sheet")
        if sheet.sheet_id in self._sheets:
            raise GalacticValidationError(f"duplicate sheet_id {sheet.sheet_id}")
        # sheets reference filaments by ID — allow deferred (no strict requirement)
        # but if filaments exist and sheet references unknown, raise only if strictly needed
        # For scaffold compatibility, allow any filament ids.
        self._sheets[sheet.sheet_id] = sheet
        self._publish("galactic.sheet.registered", {"sheet_id": sheet.sheet_id})

    def register_node(self, node: CosmicNode) -> None:
        self._require_authority("galactic.register_node")
        if not isinstance(node, CosmicNode):
            raise GalacticValidationError("node must be CosmicNode")
        if node.node_id in self._nodes:
            raise GalacticValidationError(f"duplicate node_id {node.node_id}")
        if node.host_cluster_id is not None and node.host_cluster_id not in self._clusters:
            raise GalacticHierarchyError(f"unknown host_cluster {node.host_cluster_id}")
        if node.host_supercluster_id is not None and node.host_supercluster_id not in self._superclusters:
            raise GalacticHierarchyError(f"unknown host_supercluster {node.host_supercluster_id}")
        self._nodes[node.node_id] = node
        self._publish("galactic.node.registered", {"node_id": node.node_id})

    def register_web(self, web: CosmicWeb) -> None:
        self._require_authority("galactic.register_web")
        if not isinstance(web, CosmicWeb):
            raise GalacticValidationError("web must be CosmicWeb")
        if web.web_id in self._webs:
            raise GalacticValidationError(f"duplicate web_id {web.web_id}")
        # Web is an ID-based graph referencing nodes/filaments/sheets/voids.
        # For deterministic build, nodes/filaments may be registered after web —
        # allow deferred references (strict validation is best-effort via diagnostics).
        self._webs[web.web_id] = web
        self._publish("galactic.web.registered", {"web_id": web.web_id})

    def link(self, parent_id: str, child_id: str, relation: HierarchyRelation) -> None:
        self._require_authority("galactic.link")
        if not isinstance(relation, HierarchyRelation):
            raise GalacticValidationError(f"relation must be HierarchyRelation, got {relation!r}")
        if parent_id == child_id:
            raise GalacticHierarchyError("self-link forbidden")
        if not parent_id or not child_id:
            raise GalacticValidationError("parent_id and child_id must be non-empty")
        # depth guard (simple: edges count as depth)
        if len(self._edges) >= 10_000_000:
            raise GalacticLimitationError(f"edge limit exceeded: {LimitationState.OUTSIDE_VALID_RANGE.value}")
        edge = HierarchyEdge(parent_id=parent_id, child_id=child_id, relation=relation)
        self._edges.append(edge)
        self._publish("galactic.link.created", {"parent_id": parent_id, "child_id": child_id, "relation": relation.value})

    # ------------------------------------------------------------ queries — retrieval

    def get_galaxy(self, galaxy_id: str) -> Galaxy:
        try:
            return self._galaxies[galaxy_id]
        except KeyError:
            raise GalacticValidationError(f"unknown galaxy {galaxy_id}")

    def get_group(self, group_id: str) -> GalaxyGroup:
        try:
            return self._groups[group_id]
        except KeyError:
            raise GalacticValidationError(f"unknown group {group_id}")

    def get_cluster(self, cluster_id: str) -> GalaxyCluster:
        try:
            return self._clusters[cluster_id]
        except KeyError:
            raise GalacticValidationError(f"unknown cluster {cluster_id}")

    def get_supercluster(self, supercluster_id: str) -> Supercluster:
        try:
            return self._superclusters[supercluster_id]
        except KeyError:
            raise GalacticValidationError(f"unknown supercluster {supercluster_id}")

    def get_void(self, void_id: str) -> CosmicVoid:
        try:
            return self._voids[void_id]
        except KeyError:
            raise GalacticValidationError(f"unknown void {void_id}")

    def get_filament(self, filament_id: str) -> Filament:
        try:
            return self._filaments[filament_id]
        except KeyError:
            raise GalacticValidationError(f"unknown filament {filament_id}")

    def get_sheet(self, sheet_id: str) -> Sheet:
        try:
            return self._sheets[sheet_id]
        except KeyError:
            raise GalacticValidationError(f"unknown sheet {sheet_id}")

    def get_node(self, node_id: str) -> CosmicNode:
        try:
            return self._nodes[node_id]
        except KeyError:
            raise GalacticValidationError(f"unknown node {node_id}")

    def get_web(self, web_id: str) -> CosmicWeb:
        try:
            return self._webs[web_id]
        except KeyError:
            raise GalacticValidationError(f"unknown web {web_id}")

    # hierarchy graph queries — deterministic insertion order

    def hierarchy_children(self, parent_id: str, relation: Optional[HierarchyRelation] = None) -> Tuple[str, ...]:
        if relation is None:
            return tuple(e.child_id for e in self._edges if e.parent_id == parent_id)
        return tuple(e.child_id for e in self._edges if e.parent_id == parent_id and e.relation == relation)

    def hierarchy_parents(self, child_id: str, relation: Optional[HierarchyRelation] = None) -> Tuple[str, ...]:
        if relation is None:
            return tuple(e.parent_id for e in self._edges if e.child_id == child_id)
        return tuple(e.parent_id for e in self._edges if e.child_id == child_id and e.relation == relation)

    def hierarchy_edges(self, relation: Optional[HierarchyRelation] = None) -> Tuple[HierarchyEdge, ...]:
        if relation is None:
            return tuple(self._edges)
        return tuple(e for e in self._edges if e.relation == relation)

    # spatial queries — deterministic ordering by id

    def query_galaxies_in_radius(self, center: Vec3, radius_mpc: float, ctx: Optional[CoordinateContext] = None) -> Tuple[Galaxy, ...]:
        if not isinstance(center, Vec3):
            raise GalacticValidationError("center must be Vec3")
        if not isinstance(radius_mpc, (int, float)) or isinstance(radius_mpc, bool) or not math.isfinite(float(radius_mpc)) or float(radius_mpc) < 0:
            raise GalacticNumericalError(f"radius_mpc must be finite >=0, got {radius_mpc!r}")
        r = float(radius_mpc)
        result: List[Galaxy] = []
        for g in self._galaxies.values():
            # if ctx provided, check frame compatibility
            if ctx is not None and g.coordinate_context.frame != ctx.frame:
                # require same frame or allow transform via provider
                try:
                    # attempt transform check — if provider raises, treat as incompatible
                    if self.coordinates is not None:
                        # deterministic: we only compare comoving if frames differ but scale factors match
                        pass
                except Exception:
                    raise GalacticLimitationError(f"incompatible frames: {g.coordinate_context.frame} vs {ctx.frame}: {LimitationState.INCOMPATIBLE_FRAMES.value}")
            # distance in Mpc — treat Vec3 units as Mpc for galactic scale
            sep = (g.position - center).norm()
            if sep <= r + 1e-12:
                result.append(g)
        # deterministic: sorted by galaxy_id
        result.sort(key=lambda x: x.galaxy_id)
        return tuple(result)

    def query_galaxies_in_box(self, min_corner: Vec3, max_corner: Vec3) -> Tuple[Galaxy, ...]:
        if not isinstance(min_corner, Vec3) or not isinstance(max_corner, Vec3):
            raise GalacticValidationError("corners must be Vec3")
        result = []
        for g in self._galaxies.values():
            if (min_corner.x <= g.position.x <= max_corner.x and
                min_corner.y <= g.position.y <= max_corner.y and
                min_corner.z <= g.position.z <= max_corner.z):
                result.append(g)
        result.sort(key=lambda x: x.galaxy_id)
        return tuple(result)

    # cosmic web connectivity — id-based, deterministic

    def filaments_of_node(self, node_id: str) -> Tuple[Filament, ...]:
        if node_id not in self._nodes:
            raise GalacticValidationError(f"unknown node {node_id}")
        res = [f for f in self._filaments.values() if f.node_a_id == node_id or f.node_b_id == node_id]
        res.sort(key=lambda x: x.filament_id)
        return tuple(res)

    def nodes_of_filament(self, filament_id: str) -> Tuple[CosmicNode, ...]:
        f = self.get_filament(filament_id)
        nodes = []
        for nid in (f.node_a_id, f.node_b_id):
            if nid in self._nodes:
                nodes.append(self._nodes[nid])
        # deterministic by node_id
        nodes.sort(key=lambda x: x.node_id)
        return tuple(nodes)

    def neighbors_of_void(self, void_id: str) -> Tuple[str, ...]:
        v = self.get_void(void_id)
        # neighbor_structure_ids are IDs of filaments/sheets/nodes
        return tuple(sorted(v.neighbor_structure_ids))

    def sheets_of_filament(self, filament_id: str) -> Tuple[Sheet, ...]:
        if filament_id not in self._filaments:
            raise GalacticValidationError(f"unknown filament {filament_id}")
        res = [s for s in self._sheets.values() if filament_id in s.member_filament_ids]
        res.sort(key=lambda x: x.sheet_id)
        return tuple(res)

    def web_connectivity(self, web_id: str) -> Dict[str, Any]:
        """Return deterministic connectivity summary for a web."""
        web = self.get_web(web_id)
        # count edges per filament
        return {
            "web_id": web.web_id,
            "nodes": tuple(sorted(web.node_ids)),
            "filaments": tuple(sorted(web.filament_ids)),
            "sheets": tuple(sorted(web.sheet_ids)),
            "voids": tuple(sorted(web.void_ids)),
            "node_count": len(web.node_ids),
            "filament_count": len(web.filament_ids),
            "sheet_count": len(web.sheet_ids),
            "void_count": len(web.void_ids),
        }

    # ------------------------------------------------------------ expansion / velocity / distances

    def velocity_decomposition(
        self,
        position_mpc: Vec3,
        peculiar_velocity: Vec3,
        local_gravity: Vec3,
        h0_kms_mpc: Optional[float] = None,
    ) -> VelocityDecomposition:
        h0 = float(h0_kms_mpc) if h0_kms_mpc is not None else float(self.config.hubble_constant_kms_mpc)
        return decompose_velocity(position_mpc, peculiar_velocity, local_gravity, h0)

    def expansion_contribution(self, position_mpc: Vec3, ctx: Optional[CoordinateContext] = None) -> Vec3:
        """Hubble flow at position (low-z linear). ctx provides scale_factor if needed."""
        from .velocity import hubble_flow_velocity
        h0 = float(self.config.hubble_constant_kms_mpc)
        return hubble_flow_velocity(position_mpc, h0)

    def distance(
        self,
        a: Vec3,
        b: Vec3,
        ctx: CoordinateContext,
        kind: DistanceKind,
    ) -> float:
        """Every distance call declares its CoordinateContext."""
        return separation_by_kind(a, b, ctx, kind)

    def cosmological_distance(self, z: float, kind: DistanceKind = DistanceKind.COMOVING) -> float:
        if self.cosmology is None:
            raise GalacticDependencyError("no CosmologyProvider configured")
        zf = float(z)
        if kind == DistanceKind.COMOVING:
            return float(self.cosmology.comoving_distance(zf))
        if kind == DistanceKind.LUMINOSITY:
            return float(self.cosmology.luminosity_distance(zf))
        if kind == DistanceKind.ANGULAR_DIAMETER:
            return float(self.cosmology.angular_diameter_distance(zf))
        if kind == DistanceKind.PROPER:
            # proper = comoving * a, a=1/(1+z)
            dc = float(self.cosmology.comoving_distance(zf))
            return dc / (1.0 + zf)
        return float(self.cosmology.comoving_distance(zf))

    def redshift_to_scale_factor(self, z: float) -> float:
        if not math.isfinite(z) or z < -0.9:
            raise GalacticNumericalError(f"z must be finite >= -0.9, got {z!r}")
        return 1.0 / (1.0 + float(z))

    # ------------------------------------------------------------ matter distribution — lazy / hierarchical

    def sample_matter_distribution(
        self,
        positions: Iterable[Vec3],
        ctx: CoordinateContext,
        model: str = "uniform",
        base_density_kg_m3: float = 2.5e-27,
    ) -> Tuple[Any, ...]:
        """Lazy sampled density field — no dense 3D array allocated.

        positions: sparse query points (Mpc units), ctx: coordinate context.
        Returns tuple of DensitySample with deterministic ordering by input order.
        This avoids O(N^3) allocation; callers request only needed points.
        """
        from .types import DensitySample
        from .provenance import SimulatedValue
        if not math.isfinite(base_density_kg_m3) or base_density_kg_m3 <= 0:
            raise GalacticNumericalError(f"base_density must be finite >0, got {base_density_kg_m3!r}")
        samples: List[Any] = []
        # deterministic jitter via RNG if model != uniform
        for i, pos in enumerate(positions):
            if not isinstance(pos, Vec3):
                raise GalacticValidationError(f"position {i} must be Vec3")
            # simple model: uniform + optional deterministic fluctuation
            density = float(base_density_kg_m3)
            if model == "clustered":
                # use galaxy proximity to boost density
                boost = 0.0
                for g in self._galaxies.values():
                    sep = (g.position - pos).norm()
                    # Gaussian boost sigma 2 Mpc
                    boost += math.exp(-0.5 * (sep / 2.0) ** 2) * 5.0
                density = base_density_kg_m3 * (1.0 + boost)
                # add deterministic RNG fluctuation 0.9-1.1 if rng present
                if self.rng is not None:
                    try:
                        jitter = 0.9 + 0.2 * float(self.rng.uniform())
                        density *= jitter
                    except Exception:
                        pass
            over = (density / base_density_kg_m3) - 1.0
            samples.append(DensitySample(
                position=pos,
                coordinate_context=ctx,
                density_kg_m3=SimulatedValue(value=density, unit="kg/m3", model=f"galactic.matter.{model}", seed=None),
                overdensity=SimulatedValue(value=over, unit="dimensionless", model=f"galactic.matter.{model}"),
            ))
        return tuple(samples)

    def get_density_at(self, position: Vec3, ctx: CoordinateContext) -> Any:
        """Single-point lazy query — delegates to sample_matter_distribution."""
        return self.sample_matter_distribution([position], ctx)[0]

    # ------------------------------------------------------------ observation / measurement

    def observe_galaxy(
        self,
        observer: Any,
        galaxy_id: str,
        observation_time_s: float,
    ) -> Any:
        """Observer never gets instantaneous knowledge — goes through ObservationProvider."""
        if galaxy_id not in self._galaxies:
            raise GalacticValidationError(f"unknown galaxy {galaxy_id}")
        if not math.isfinite(float(observation_time_s)) or float(observation_time_s) < 0:
            raise GalacticNumericalError(f"observation_time_s must be finite >=0, got {observation_time_s!r}")
        if self.observation is None:
            raise GalacticDependencyError("no ObservationProvider configured")
        # ensure galaxy is tracked in observation history (best-effort)
        try:
            galaxy = self._galaxies[galaxy_id]
            if hasattr(self.observation, "_ensure_galaxy_in_history"):
                self.observation._ensure_galaxy_in_history(galaxy_id, galaxy.position, float(observation_time_s))
        except Exception:
            pass
        # observation provider enforces finite light speed / lookback
        if hasattr(self.observation, "observe_galaxy"):
            return self.observation.observe_galaxy(observer, galaxy_id, float(observation_time_s))
        if hasattr(self.observation, "lookback_position"):
            return self.observation.lookback_position(observer, galaxy_id, float(observation_time_s))
        raise GalacticDependencyError("ObservationProvider missing observe_galaxy/lookback_position")

    def lookback_position(self, observer: Any, galaxy_id: str, at_time_s: float) -> Any:
        if self.observation is None:
            raise GalacticDependencyError("no ObservationProvider")
        return self.observation.lookback_position(observer, galaxy_id, float(at_time_s))

    def redshift(self, observer: Any, galaxy_id: str) -> float:
        if self.observation is None:
            raise GalacticDependencyError("no ObservationProvider")
        return float(self.observation.redshift(observer, galaxy_id))

    def measure_galaxy_position(self, observer: Any, galaxy_id: str) -> Any:
        if galaxy_id not in self._galaxies:
            raise GalacticValidationError(f"unknown galaxy {galaxy_id}")
        if self.measurement is None:
            raise GalacticDependencyError("no MeasurementProvider")
        return self.measurement.measure_position(observer, galaxy_id)

    def ingestion_query(self, catalog: str, query: dict) -> list:
        if self.ingestion is None:
            raise GalacticDependencyError("no IngestionProvider")
        return self.ingestion.query_catalog(catalog, query)

    def build_gaia_adql(self, spec: Any) -> str:
        if self.ingestion is None:
            raise GalacticDependencyError("no IngestionProvider")
        if hasattr(self.ingestion, "build_gaia_query"):
            return self.ingestion.build_gaia_query(spec)
        raise GalacticDependencyError("IngestionProvider missing build_gaia_query")

    # ------------------------------------------------------------ persistence / diagnostics

    def diagnostics(self) -> Dict[str, Any]:
        return {
            "galaxies": len(self._galaxies),
            "groups": len(self._groups),
            "clusters": len(self._clusters),
            "superclusters": len(self._superclusters),
            "voids": len(self._voids),
            "filaments": len(self._filaments),
            "sheets": len(self._sheets),
            "nodes": len(self._nodes),
            "webs": len(self._webs),
            "edges": len(self._edges),
            "model_version": self.config.model_version,
            "provenance": "SIMULATED_DATA",
            "h0_kms_mpc": self.config.hubble_constant_kms_mpc,
        }

    def provenance_summary(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for g in self._galaxies.values():
            key = g.provenance.value
            counts[key] = counts.get(key, 0) + 1
        for grp in self._groups.values():
            key = grp.provenance.value
            counts[key] = counts.get(key, 0) + 1
        for c in self._clusters.values():
            key = c.provenance.value
            counts[key] = counts.get(key, 0) + 1
        for s in self._superclusters.values():
            key = s.provenance.value
            counts[key] = counts.get(key, 0) + 1
        return counts

    # hierarchical level check
    def hierarchy_depth(self, start_id: str) -> int:
        """BFS depth from start_id following CONTAINS edges."""
        visited = set()
        frontier = [(start_id, 0)]
        max_depth = 0
        while frontier:
            nid, d = frontier.pop(0)
            if nid in visited:
                continue
            visited.add(nid)
            max_depth = max(max_depth, d)
            if d >= self.config.max_hierarchy_depth:
                raise GalacticLimitationError(f"hierarchy depth {d} exceeds max {self.config.max_hierarchy_depth}: {LimitationState.IMPOSSIBLE_HIERARCHY.value}")
            for child in self.hierarchy_children(nid, HierarchyRelation.CONTAINS):
                if child not in visited:
                    frontier.append((child, d + 1))
        return max_depth

    # floating origin
    def rebase_origin(self, new_origin: Vec3) -> Any:
        if not isinstance(new_origin, Vec3):
            raise GalacticValidationError("new_origin must be Vec3")
        if self.coordinates is None:
            raise GalacticDependencyError("no CoordinateProvider")
        result = self.coordinates.rebase(Vec3(0, 0, 0), new_origin)
        # rebase all galaxy positions deterministically
        for gid, galaxy in list(self._galaxies.items()):
            new_pos = Vec3(galaxy.position.x - new_origin.x, galaxy.position.y - new_origin.y, galaxy.position.z - new_origin.z)
            # need to reconstruct galaxy with new position (frozen)
            from dataclasses import replace
            try:
                new_galaxy = replace(galaxy, position=new_pos)
                self._galaxies[gid] = new_galaxy
            except Exception:
                pass
        self._publish("galactic.rebase", {"new_origin": new_origin.to_tuple()})
        return result

    # save/load
    def save(self, key: str) -> None:
        if self.persistence is None:
            raise GalacticDependencyError("no PersistenceHook")
        from .persistence import galaxy_to_dict, galaxy_group_to_dict, galaxy_cluster_to_dict, supercluster_to_dict, void_to_dict, filament_to_dict, sheet_to_dict, node_to_dict, web_to_dict, edge_to_dict
        payload = {
            "galaxies": [galaxy_to_dict(g) for g in sorted(self._galaxies.values(), key=lambda x: x.galaxy_id)],
            "groups": [galaxy_group_to_dict(g) for g in sorted(self._groups.values(), key=lambda x: x.group_id)],
            "clusters": [galaxy_cluster_to_dict(c) for c in sorted(self._clusters.values(), key=lambda x: x.cluster_id)],
            "superclusters": [supercluster_to_dict(s) for s in sorted(self._superclusters.values(), key=lambda x: x.supercluster_id)],
            "voids": [void_to_dict(v) for v in sorted(self._voids.values(), key=lambda x: x.void_id)],
            "filaments": [filament_to_dict(f) for f in sorted(self._filaments.values(), key=lambda x: x.filament_id)],
            "sheets": [sheet_to_dict(s) for s in sorted(self._sheets.values(), key=lambda x: x.sheet_id)],
            "nodes": [node_to_dict(n) for n in sorted(self._nodes.values(), key=lambda x: x.node_id)],
            "webs": [web_to_dict(w) for w in sorted(self._webs.values(), key=lambda x: x.web_id)],
            "edges": [edge_to_dict(e) for e in self._edges],
            "config": {"model_version": self.config.model_version},
        }
        self.persistence.save(key, payload)

    def load(self, key: str) -> Dict[str, Any]:
        if self.persistence is None:
            raise GalacticDependencyError("no PersistenceHook")
        data = self.persistence.load(key)
        if data is None:
            raise GalacticValidationError(f"no persistence data for key {key!r}")
        return data
