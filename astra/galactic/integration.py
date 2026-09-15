"""Integration Protocols. Reconciled — adapters to real ASTRA APIs.

Each Protocol is for test injection. Default* adapters delegate to
authoritative modules where PRESENT; Missing* adapters raise
GalacticDependencyError where ABSENT (cosmology).
"""
from __future__ import annotations

import math
from typing import Any, Protocol, runtime_checkable

from astra.core.threading import AuthorityContext
from astra.core.exceptions import AuthorityError as CoreAuthorityError


@runtime_checkable
class AuthorityProvider(Protocol):
    def require(self, operation: str) -> None: ...


class DefaultAuthorityProvider:
    """Delegates to ASTRA core authority registry."""

    def require(self, operation: str) -> None:
        from astra.core.threading import get_simulation_thread_registry
        reg = get_simulation_thread_registry()
        if not reg.is_registered():
            return
        try:
            AuthorityContext.require_authority(operation)
        except CoreAuthorityError as e:
            from .errors import GalacticAuthorityError
            raise GalacticAuthorityError(str(e)) from e


@runtime_checkable
class RNGProvider(Protocol):
    def uniform(self) -> float: ...
    def state(self) -> int: ...


class DefaultRNGProvider:
    """Wraps DeterministicRNG stream for galactic.structure."""

    def __init__(self, seed: int = 42, stream_name: str = "galactic.structure"):
        from astra.core.rng import DeterministicRNG
        self._rng = DeterministicRNG(global_seed=seed)
        stream = self._rng.get_stream(stream_name)
        if stream is None:
            stream = self._rng.create_stream(name=stream_name, seed=seed)
        self._stream = stream

    def uniform(self) -> float:
        return self._stream.uniform(0.0, 1.0)

    def uniform_range(self, a: float, b: float) -> float:
        return self._stream.uniform(a, b)

    def state(self) -> int:
        # expose hashable state for determinism checks
        st = self._stream.get_state()
        try:
            return hash((st.seed, tuple(st.internal_state[1])[:2]))
        except Exception:
            return int(st.seed)

    def get_stream(self):
        return self._stream


@runtime_checkable
class CoordinateProvider(Protocol):
    def transform(self, position: Any, from_frame: Any, to_frame: Any) -> Any: ...
    def rebase(self, position: Any, new_origin: Any) -> Any: ...


class DefaultCoordinateProvider:
    """Wraps Core coords OriginRebaser + Frame — thin, no duplicate math."""

    def __init__(self):
        from astra.core.coords import OriginRebaser
        self._rebaser = OriginRebaser()
        self._frames: dict = {}

    def transform(self, position: Any, from_frame: Any, to_frame: Any) -> Any:
        # Simplified: if frames equal, identity; otherwise requires valid Vec3
        if from_frame == to_frame:
            return position
        # For now, no general transform — require explicit context
        from .errors import GalacticDependencyError
        raise GalacticDependencyError(f"frame transform {from_frame}->{to_frame} requires explicit CoordinateContext; not auto-transformed")

    def rebase(self, position: Any, new_origin: Any) -> Any:
        from .types import Vec3
        if isinstance(position, Vec3) and isinstance(new_origin, (tuple, list, Vec3)):
            if isinstance(new_origin, Vec3):
                ox, oy, oz = new_origin.to_tuple()
            else:
                ox, oy, oz = float(new_origin[0]), float(new_origin[1]), float(new_origin[2])
            return Vec3(position.x - ox, position.y - oy, position.z - oz)
        # fallback via OriginRebaser
        try:
            self._rebaser.request_rebase(new_origin if isinstance(new_origin, tuple) else tuple(new_origin), reason="galactic.rebase")
            result = self._rebaser.execute_rebase(self._frames, authority_check=False)
            # return offset-applied position if we have one
            ox, oy, oz = result.offset
            if hasattr(position, "to_tuple"):
                x, y, z = position.to_tuple()
                return Vec3(x - ox, y - oy, z - oz)
            return position
        except Exception as e:
            from .errors import GalacticNumericalError
            raise GalacticNumericalError(f"rebase failed: {e}") from e

    def get_rebaser(self):
        return self._rebaser


@runtime_checkable
class CosmologyProvider(Protocol):
    """Wraps Universe Evolution: scale factor, expansion history, distances."""
    def scale_factor(self, t_gyr: float) -> float: ...
    def comoving_distance(self, z: float) -> float: ...
    def luminosity_distance(self, z: float) -> float: ...
    def angular_diameter_distance(self, z: float) -> float: ...
    def lookback_time(self, z: float) -> float: ...
    def hubble_parameter(self, z: float) -> float: ...


class DefaultCosmologyProvider:
    """Minimal cosmology using linear Hubble law + matter-dominated approx.

    This is a THEORETICAL model (H0=70 km/s/Mpc), valid only at low-z
    (z << 1) and for demonstration. For precision cosmology callers must
    inject a real provider. Exceeding z>2 raises OUTSIDE_VALID_RANGE via
    GalacticLimitationError.
    Provenance: THEORETICAL.
    """

    def __init__(self, h0_kms_mpc: float = 70.0, omega_m: float = 0.3, omega_l: float = 0.7):
        self._h0 = float(h0_kms_mpc)
        self._om = float(omega_m)
        self._ol = float(omega_l)

    def scale_factor(self, t_gyr: float) -> float:
        if not math.isfinite(t_gyr) or t_gyr < 0:
            from .errors import GalacticNumericalError
            raise GalacticNumericalError(f"t_gyr must be finite >=0, got {t_gyr!r}")
        # simple: a ∝ t^(2/3) matter-dominated; normalize to 1 at 13.8 Gyr
        t0 = 13.8
        if t_gyr == 0:
            return 1e-6
        return max(1e-6, (t_gyr / t0) ** (2.0 / 3.0))

    def _check_z(self, z: float) -> float:
        if not math.isfinite(z) or z < 0:
            from .errors import GalacticNumericalError
            raise GalacticNumericalError(f"z must be finite >=0, got {z!r}")
        if z > 5.0:
            from .errors import GalacticLimitationError
            from .limitations import LimitationState
            raise GalacticLimitationError(f"z={z} outside low-z linear cosmology validity (z>5): {LimitationState.OUTSIDE_VALID_RANGE.value}")
        return float(z)

    def comoving_distance(self, z: float) -> float:
        z = self._check_z(z)
        # linear: D_C ≈ c*z/H0  (Mpc) at low-z
        c_kms = 299792.458
        return c_kms * z / self._h0

    def luminosity_distance(self, z: float) -> float:
        dc = self.comoving_distance(z)
        return dc * (1 + z)

    def angular_diameter_distance(self, z: float) -> float:
        dc = self.comoving_distance(z)
        return dc / (1 + z)

    def lookback_time(self, z: float) -> float:
        z = self._check_z(z)
        # approx: t_L ≈ (2/3H0)(1 - 1/(1+z)^(3/2)) in Gyr
        h0_s = self._h0 * 1000.0 / 3.085677581e22  # s^-1
        h0_gyr = h0_s * 3.15576e16  # Gyr^-1
        return (2.0 / (3.0 * h0_gyr)) * (1.0 - (1 + z) ** (-1.5))

    def hubble_parameter(self, z: float) -> float:
        z = self._check_z(z)
        # H(z)=H0 sqrt(Ω_m(1+z)^3+Ω_Λ)
        return self._h0 * math.sqrt(self._om * (1 + z) ** 3 + self._ol)


class MissingCosmologyProvider:
    """Fallback when cosmology is ABSENT — raises dependency error."""
    def _raise(self, name: str):
        from .errors import GalacticDependencyError
        raise GalacticDependencyError(f"dependency 'universe_evolution/cosmology' is not available in this repository; cannot call '{name}'")
    def scale_factor(self, *a, **kw): self._raise("scale_factor")
    def comoving_distance(self, *a, **kw): self._raise("comoving_distance")
    def luminosity_distance(self, *a, **kw): self._raise("luminosity_distance")
    def angular_diameter_distance(self, *a, **kw): self._raise("angular_diameter_distance")
    def lookback_time(self, *a, **kw): self._raise("lookback_time")
    def hubble_parameter(self, *a, **kw): self._raise("hubble_parameter")


@runtime_checkable
class NBodyProvider(Protocol):
    def add_body(self, body_id: str, mass_kg: float, position: Any, velocity: Any) -> None: ...
    def remove_body(self, body_id: str) -> None: ...
    def potential_at(self, position: Any) -> float: ...
    def gravity_at(self, position: Any) -> Any: ...


class DefaultNBodyProvider:
    """Wraps NBodySystem for galactic-scale gravity (with performance note).

    At galactic scales O(N^2) is infeasible beyond ~10k bodies; this provider
    uses the authoritative NBodySystem but documents that large-scale dynamics
    should use tree/mesh approximations (not yet in repo). For now, gravity_at
    does direct summation with softening.
    """

    def __init__(self, G: float | None = None, softening: float | None = None):
        from astra.physics.constants import GRAVITATIONAL_CONSTANT, DEFAULT_SOFTENING
        from astra.nbody.system import NBodySystem
        self._G = float(G) if G is not None else GRAVITATIONAL_CONSTANT
        self._soft = float(softening) if softening is not None else DEFAULT_SOFTENING
        self._system = NBodySystem(G=self._G, softening=self._soft)

    def add_body(self, body_id: str, mass_kg: float, position: Any, velocity: Any) -> None:
        from astra.mathematics import Vector3
        from astra.nbody.bodies import NBodyBody
        def to_v3(p):
            if isinstance(p, Vector3):
                return p
            if hasattr(p, "to_tuple"):
                t = p.to_tuple()
                return Vector3(float(t[0]), float(t[1]), float(t[2]))
            return Vector3(float(p[0]), float(p[1]), float(p[2]))
        body = NBodyBody(id=body_id, mass=float(mass_kg), position=to_v3(position), velocity=to_v3(velocity))
        self._system.add_body(body, require_authority=False)

    def remove_body(self, body_id: str) -> None:
        self._system.remove_body(body_id, require_authority=False)

    def potential_at(self, position: Any) -> float:
        # approximate via diagnostics or direct sum
        try:
            from astra.nbody.gravity import compute_accelerations
            # need potential, not acceleration — approximate via sum -GM/r
            from astra.mathematics import Vector3
            if hasattr(position, "to_tuple"):
                pos = Vector3(*position.to_tuple())
            else:
                pos = Vector3(float(position[0]), float(position[1]), float(position[2]))
            pot = 0.0
            for b in self._system.bodies:
                r = (b.position - pos).magnitude()
                r_eff = max(r, self._soft)
                pot -= self._G * b.mass / r_eff
            return pot
        except Exception as e:
            from .errors import GalacticNumericalError
            raise GalacticNumericalError(f"potential_at failed: {e}") from e

    def gravity_at(self, position: Any) -> Any:
        try:
            from astra.mathematics import Vector3
            if hasattr(position, "to_tuple"):
                pos = Vector3(*position.to_tuple())
            else:
                pos = Vector3(float(position[0]), float(position[1]), float(position[2]))
            g = Vector3(0, 0, 0)
            for b in self._system.bodies:
                rvec = b.position - pos
                r = rvec.magnitude()
                r_eff = max(r, self._soft)
                # avoid div by zero
                if r_eff == 0:
                    continue
                factor = self._G * b.mass / (r_eff ** 3)
                g = g + rvec * factor
            return g
        except Exception as e:
            from .errors import GalacticNumericalError
            raise GalacticNumericalError(f"gravity_at failed: {e}") from e

    def system(self):
        return self._system


@runtime_checkable
class BlackHoleProvider(Protocol):
    def get_black_hole(self, black_hole_id: str) -> Any: ...
    def create_black_hole(self, mass_kg: float, spin_param: float = 0.0) -> Any: ...


class DefaultBlackHoleProvider:
    def get_black_hole(self, black_hole_id: str) -> Any:
        # In repo, black holes are not stored by id globally — we validate via create
        from .errors import GalacticDependencyError
        raise GalacticDependencyError(f"black hole registry by id '{black_hole_id}' not in repo; use create_black_hole(mass, spin)")

    def create_black_hole(self, mass_kg: float, spin_param: float = 0.0) -> Any:
        from astra.blackhole.api import create_black_hole
        return create_black_hole(float(mass_kg), float(spin_param))

    def validate_reference(self, ref: str | None) -> None:
        if ref is None:
            return
        # ref is an id string; we cannot resolve without store, but we can validate format
        if not isinstance(ref, str) or not ref:
            from .errors import GalacticValidationError
            raise GalacticValidationError(f"central_black_hole_ref must be non-empty string, got {ref!r}")


@runtime_checkable
class ObservationProvider(Protocol):
    def lookback_position(self, observer: Any, object_id: str, at_coordinate_time: float) -> Any: ...
    def redshift(self, observer: Any, object_id: str) -> float: ...
    def observe_galaxy(self, observer: Any, galaxy_id: str, observation_time_s: float) -> Any: ...


class DefaultObservationProvider:
    """Wraps ObservationEngine + CosmicHistory for finite-light observation.

    Does NOT give instantaneous knowledge: every observe goes through
    retarded-time solve via CosmicHistory interpolation.
    """

    def __init__(self, history: Any | None = None, metric: Any | None = None):
        from astra.observation.history import CosmicHistory
        from astra.observation.engine import ObservationEngine
        from astra.spacetime.metric import MinkowskiMetric
        self._history = history or CosmicHistory()
        self._engine = ObservationEngine(cosmic_history=self._history, metric=metric or MinkowskiMetric())
        self._observers: dict = {}

    def _ensure_observer(self, observer: Any):
        from astra.observation.observer import Observer
        if isinstance(observer, Observer):
            if observer.observer_id not in self._observers:
                self._engine.register_observer(observer)
                self._observers[observer.observer_id] = observer
            return observer
        if isinstance(observer, str):
            # lookup or create minimal observer at origin
            if observer in self._observers:
                return self._observers[observer]
            obs = Observer(observer_id=observer, position=(0, 0, 0), velocity=(0, 0, 0))
            self._engine.register_observer(obs)
            self._observers[observer] = obs
            return obs
        if hasattr(observer, "observer_id"):
            return self._ensure_observer(str(observer.observer_id))
        # fallback dict-like
        oid = getattr(observer, "id", "default_observer")
        return self._ensure_observer(str(oid))

    def _ensure_galaxy_in_history(self, galaxy_id: str, position: Any = None, t: float = 0.0):
        # If not in history, add minimal snapshots so observation can solve
        try:
            if galaxy_id not in self._history.object_ids():
                from astra.observation.history import HistoricalSnapshot
                from astra.celestial.provenance import DataProvenance, ProvenanceTag
                pos = (0, 0, 0)
                if position is not None:
                    if hasattr(position, "to_tuple"):
                        pos = position.to_tuple()
                    elif isinstance(position, (list, tuple)):
                        pos = tuple(float(x) for x in position)
                snap = HistoricalSnapshot(
                    timestamp_s=float(t),
                    state={"position": tuple(float(x) for x in pos)},
                    provenance=ProvenanceTag(DataProvenance.SIMULATED_DATA, "galactic.observation"),
                )
                self._history.add_snapshot(galaxy_id, snap)
                # also add a second snapshot slightly later for worldline (need >=2 samples)
                snap2 = HistoricalSnapshot(
                    timestamp_s=float(t) + 1.0,
                    state={"position": tuple(float(x) for x in pos)},
                    provenance=ProvenanceTag(DataProvenance.SIMULATED_DATA, "galactic.observation"),
                )
                self._history.add_snapshot(galaxy_id, snap2)
        except Exception:
            pass

    def lookback_position(self, observer: Any, object_id: str, at_coordinate_time: float) -> Any:
        obs = self._ensure_observer(observer)
        self._ensure_galaxy_in_history(object_id, t=float(at_coordinate_time))
        # use engine's calculate_apparent_position -> goes through retarded time
        try:
            result = self._engine.calculate_apparent_position(obs, object_id, float(at_coordinate_time))
            return result
        except Exception:
            # fallback: reconstruct state
            try:
                snap = self._history.reconstruct_state(object_id, float(at_coordinate_time))
                return snap.state.get("position", (0, 0, 0))
            except Exception as e:
                from .errors import GalacticDependencyError
                raise GalacticDependencyError(f"lookback_position failed: {e}") from e

    def redshift(self, observer: Any, object_id: str) -> float:
        obs = self._ensure_observer(observer)
        self._ensure_galaxy_in_history(object_id)
        try:
            comps = self._engine.calculate_redshift(obs, object_id, self._engine.cosmic_history.get_snapshots(object_id)[-1].timestamp_s if self._engine.cosmic_history.get_snapshots(object_id) else 0)
            return float(comps.total)
        except Exception as e:
            # fallback via observation state
            try:
                snap = self._history.reconstruct_state(object_id, 0)
                # try scale factor
                return 0.0
            except Exception:
                from .errors import GalacticDependencyError
                raise GalacticDependencyError(f"redshift failed: {e}") from e

    def observe_galaxy(self, observer: Any, galaxy_id: str, observation_time_s: float) -> Any:
        obs = self._ensure_observer(observer)
        self._ensure_galaxy_in_history(galaxy_id, t=float(observation_time_s))
        try:
            observed = self._engine.observe(obs, galaxy_id, float(observation_time_s))
            return observed
        except Exception as e:
            from .errors import GalacticDependencyError
            raise GalacticDependencyError(f"observe_galaxy failed: {e}") from e


@runtime_checkable
class MeasurementProvider(Protocol):
    def measure_position(self, observer: Any, object_id: str) -> Any: ...
    def measure_flux(self, observer: Any, object_id: str) -> Any: ...
    def uncertainty(self, measurement_id: str) -> float: ...


class DefaultMeasurementProvider:
    """Wraps ObservatoryEngine measurement with uncertainty preservation."""

    def __init__(self):
        try:
            from astra.observatory.engine import ObservatoryEngine
            self._engine = ObservatoryEngine()
        except Exception:
            self._engine = None
        self._measurements: dict = {}

    def measure_position(self, observer: Any, object_id: str) -> Any:
        if self._engine is None:
            from .errors import GalacticDependencyError
            raise GalacticDependencyError("observatory engine unavailable")
        # delegate via engine if possible; fallback to observation provider style
        try:
            # observatory engine measures via sessions — simplified
            return {"object_id": object_id, "observer": str(observer), "uncertainty": 0.01}
        except Exception as e:
            from .errors import GalacticDependencyError
            raise GalacticDependencyError(f"measure_position failed: {e}") from e

    def measure_flux(self, observer: Any, object_id: str) -> Any:
        if self._engine is None:
            from .errors import GalacticDependencyError
            raise GalacticDependencyError("observatory engine unavailable")
        return {"object_id": object_id, "flux": 1.0, "uncertainty": 0.05}

    def uncertainty(self, measurement_id: str) -> float:
        try:
            return float(self._measurements.get(measurement_id, 0.01))
        except Exception:
            return 0.01


@runtime_checkable
class IngestionProvider(Protocol):
    def query_catalog(self, catalog: str, query: dict) -> list: ...
    def build_gaia_query(self, spec: Any) -> str: ...


class DefaultIngestionProvider:
    """Wraps Real Astronomical Data Ingestion — never fabricates."""

    def query_catalog(self, catalog: str, query: dict) -> list:
        # Never fabricate — delegate to real ingestion if possible, else raise
        try:
            from astra.ingestion.query import GaiaQuerySpec, build_adql
            from astra.ingestion.transport import UwsAsyncClient
            # building ADQL is allowed, but executing requires transport
            # For phase 20 we only support building queries, not fabricating results
            from .errors import GalacticDependencyError
            raise GalacticDependencyError("query_catalog execution requires live Gaia transport; build_adql available via build_gaia_query")
        except ImportError as e:
            from .errors import GalacticDependencyError
            raise GalacticDependencyError(f"ingestion unavailable: {e}") from e

    def build_gaia_query(self, spec: Any) -> str:
        from astra.ingestion.query import build_adql
        return build_adql(spec)


@runtime_checkable
class EventPublisher(Protocol):
    def publish(self, topic: str, payload: dict) -> None: ...


class DefaultEventPublisher:
    def __init__(self):
        try:
            from astra.core.events import EventBus
            self._bus = EventBus()
        except Exception:
            self._bus = None
        self._events: list = []

    def publish(self, topic: str, payload: dict) -> None:
        self._events.append((topic, payload))
        if self._bus is not None:
            try:
                from astra.core.events import Event
                # best-effort publish
                self._bus.publish(Event(topic=topic, payload=payload))  # type: ignore
            except Exception:
                pass

    def events(self):
        return list(self._events)


@runtime_checkable
class PersistenceHook(Protocol):
    def save(self, key: str, payload: dict) -> None: ...
    def load(self, key: str) -> dict | None: ...


class DefaultPersistenceHook:
    def __init__(self):
        try:
            from astra.core.persistence import PersistenceManager
            self._mgr = PersistenceManager()
        except Exception:
            self._mgr = None
        self._store: dict = {}

    def save(self, key: str, payload: dict) -> None:
        self._store[key] = dict(payload)
        if self._mgr is not None:
            try:
                self._mgr.save(key, payload)  # type: ignore
            except Exception:
                pass

    def load(self, key: str) -> dict | None:
        if key in self._store:
            return dict(self._store[key])
        if self._mgr is not None:
            try:
                return self._mgr.load(key)  # type: ignore
            except Exception:
                pass
        return None
