"""Galactic engine exceptions. Reconciled against ASTRA error taxonomy."""

class GalacticError(Exception):
    """Base class for galactic / large-scale-structure errors."""

class GalacticValidationError(GalacticError):
    """Invalid input, config, or structure definition."""

class GalacticAuthorityError(GalacticError):
    """Mutation attempted without authority."""

class GalacticNumericalError(GalacticError):
    """NaN, Inf, overflow, precision loss, or numerical instability."""

class GalacticDependencyError(GalacticError):
    """A required ASTRA dependency is unavailable or misused."""

class GalacticHierarchyError(GalacticError):
    """Invalid parent/child or association relationship."""

class GalacticLimitationError(GalacticError):
    """A declared limitation state was violated (e.g., approximation used outside valid range)."""
