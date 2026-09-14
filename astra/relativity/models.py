"""ASTRA COSMOS - Relativity model selection.

Contract: distinguishes physical models explicitly so downstream layers
(e.g. ``astra.nbody.integration``) can gate relativistic corrections with an
obvious ``if model == RelativityModel.SPECIAL_RELATIVITY:`` check instead of
silently switching formulations.
"""

from enum import Enum


class RelativityModel(Enum):
    """Physico-mathematical model governing a simulation or subsystem.

    - CLASSICAL: Newtonian mechanics only (v << c everywhere).
    - SPECIAL_RELATIVITY: flat Minkowski spacetime, eta = diag(-1, 1, 1, 1).
    - WEAK_FIELD: first-order gravitational corrections (Schwarzschild in
      the r >> r_s limit; time dilation and r_s guards).
    - GENERAL_RELATIVITY: full curved-spacetime treatment (future phase).
    """

    CLASSICAL = "CLASSICAL"
    SPECIAL_RELATIVITY = "SPECIAL_RELATIVITY"
    WEAK_FIELD = "WEAK_FIELD"
    GENERAL_RELATIVITY = "GENERAL_RELATIVITY"
