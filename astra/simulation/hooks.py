"""Evolution hooks for celestial/physics/orbital/N-body/spacecraft/world/relativity.

Each hook is a thin adapter that calls the authoritative subsystem's `step(dt)` if available.
No new physics equations are introduced here; this layer only orchestrates
existing implementations deterministically.
"""

from __future__ import annotations

from typing import Any, Callable, Dict


def make_physics_hook(physics_system: Any) -> Callable[[float], Any]:
    """Adapter for PhysicsSystem.step(dt)."""
    def hook(dt: float):
        if hasattr(physics_system, "step"):
            return physics_system.step(dt)
        if hasattr(physics_system, "compute_forces"):
            return physics_system.compute_forces(dt)
        raise AttributeError("physics_system has no step/compute_forces")
    return hook


def make_motion_hook(motion_system: Any) -> Callable[[float], Any]:
    def hook(dt: float):
        if hasattr(motion_system, "step"):
            return motion_system.step(dt)
        raise AttributeError("motion_system has no step")
    return hook


def make_orbital_hook(propagator: Any) -> Callable[[float], Any]:
    """For orbital propagation (e.g., Kepler propagation)."""
    def hook(dt: float):
        if hasattr(propagator, "propagate"):
            # Propagator may expect state+dt; we delegate generically
            if hasattr(propagator, "step"):
                return propagator.step(dt)
            # Try propagate with dt
            try:
                return propagator.propagate(dt)  # type: ignore
            except TypeError:
                pass
        if hasattr(propagator, "step"):
            return propagator.step(dt)
    return hook


def make_nbody_hook(nbody_system: Any) -> Callable[[float], Any]:
    def hook(dt: float):
        if hasattr(nbody_system, "step"):
            return nbody_system.step(dt)
        if hasattr(nbody_system, "integrate"):
            return nbody_system.integrate(dt)
        raise AttributeError("nbody_system has no step/integrate")
    return hook


def make_spacecraft_hook(spacecraft_system: Any) -> Callable[[float], Any]:
    def hook(dt: float):
        if hasattr(spacecraft_system, "step"):
            return spacecraft_system.step(dt)
        if hasattr(spacecraft_system, "update"):
            return spacecraft_system.update(dt)
        raise AttributeError("spacecraft_system has no step/update")
    return hook


def make_celestial_hook(celestial_manager: Any) -> Callable[[float], Any]:
    """For stellar aging/evolution hooks — only calls if evolution supported."""
    def hook(dt: float):
        # Celestial objects are definitions; evolution is via hooks if present
        if hasattr(celestial_manager, "evolve"):
            return celestial_manager.evolve(dt)
        if hasattr(celestial_manager, "tick"):
            return celestial_manager.tick(dt)
        # No-op if no evolution model — explicitly not fabricating
        return None
    return hook


def make_world_hook(world: Any) -> Callable[[float], Any]:
    def hook(dt: float):
        if hasattr(world, "tick"):
            return world.tick(dt)
        if hasattr(world, "step"):
            return world.step(dt)
        if hasattr(world, "update"):
            return world.update(dt)
        return None
    return hook


def make_relativity_hook(relativity_manager: Any) -> Callable[[float], Any]:
    def hook(dt: float):
        # Relativity calculations are per-object; evolution may update observers
        if hasattr(relativity_manager, "step"):
            return relativity_manager.step(dt)
        if hasattr(relativity_manager, "tick"):
            return relativity_manager.tick(dt)
        return None
    return hook


def make_spacetime_hook(spacetime_manager: Any) -> Callable[[float], Any]:
    def hook(dt: float):
        if hasattr(spacetime_manager, "step"):
            return spacetime_manager.step(dt)
        if hasattr(spacetime_manager, "evolve"):
            return spacetime_manager.evolve(dt)
        return None
    return hook


def make_verification_hook(verification_fn: Callable[[], Any]) -> Callable[[float], Any]:
    """Hook that runs verification after world update."""
    def hook(dt: float):
        try:
            verification_fn()
        except Exception:
            # Verification failures should not crash evolution unless critical
            # Re-raise as EvolutionError to trigger rollback
            raise
    return hook


__all__ = [
    "make_physics_hook",
    "make_motion_hook",
    "make_orbital_hook",
    "make_nbody_hook",
    "make_spacecraft_hook",
    "make_celestial_hook",
    "make_world_hook",
    "make_relativity_hook",
    "make_spacetime_hook",
    "make_verification_hook",
]
