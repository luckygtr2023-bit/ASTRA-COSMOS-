"""Alcubierre warp tests: metric math, invariants, LOCAL causality preserved."""
import math

import pytest

from astra.mathematics import Vector3
from astra.relativity.core import SPEED_OF_LIGHT as C
from astra.spacetime import MinkowskiMetric,christoffel_symbols
from astra.spacetime.api import cartesian_state_to_chart, create_event
from astra.theoretical import (
    InvalidGeometryParameterError,
    MAX_WARP_WALL_STEEPNESS,
    ScientificClassification,
    create_alcubierre_metric,
)

V = 5.0     # x c, coordinate parameter (the whole point of the model)
R = 100.0   # m
SIGMA = 1.0  # 1/m


class TestConstruction:
    def test_supercritical_velocity_admitted(self):
        # v_s is a COORDINATE parameter; no LightSpeedViolation on build.
        w = create_alcubierre_metric(V, R, SIGMA)
        assert w.velocity == V

    def test_sigma_cap(self):
        with pytest.raises(InvalidGeometryParameterError):
            create_alcubierre_metric(1.0, 10.0, 10.0 * MAX_WARP_WALL_STEEPNESS)

    def test_bad_params_rejected(self):
        for kwargs in ({"velocity": float("nan"), "radius_m": R, "wall_steepness": SIGMA},
                       {"velocity": V, "radius_m": 0.0, "wall_steepness": SIGMA},
                       {"velocity": V, "radius_m": R, "wall_steepness": -1.0},
                       {"velocity": V, "radius_m": float("inf"),
                        "wall_steepness": SIGMA}):
            with pytest.raises(InvalidGeometryParameterError):
                create_alcubierre_metric(**kwargs)

    def test_classification_speculative(self):
        assert create_alcubierre_metric(V, R, SIGMA).classification is (
            ScientificClassification.SPECULATIVE
        )


class TestMetricMath:
    def test_zero_velocity_is_minkowski(self):
        w = create_alcubierre_metric(0.0, R, SIGMA)
        m = MinkowskiMetric()
        for x in ((0.0, 0.0, 0.0, 0.0), (1e5, 3.0, -2.0, 7.0), (0.0, 50.0, 0.0, 0.0)):
            assert w.tensor(x) == m.tensor(x)

    def test_components_at_center(self):
        w = create_alcubierre_metric(V, R, SIGMA)
        g = w.tensor((0.0, 0.0, 0.0, 0.0))  # f = 1 at the bubble center
        assert g[0][0] == pytest.approx(V * V - 1.0)
        assert g[0][1] == pytest.approx(-V)
        assert g[1][1] == 1.0 and g[2][2] == 1.0 and g[3][3] == 1.0

    def test_far_field_is_minkowski(self):
        w = create_alcubierre_metric(V, R, SIGMA)
        g = w.tensor((0.0, 1e5, 0.0, 0.0))
        assert g[0][0] == pytest.approx(-1.0, rel=1e-12)
        assert abs(g[0][1]) < 1e-12

    def test_determinant_is_minus_one_everywhere(self):
        # Lanczos-form invariant: det(g) = -1 for ALL parameters/points.
        w = create_alcubierre_metric(V, R, SIGMA)
        for x in ((0.0, 0.0, 0.0, 0.0), (0.0, R, 0.0, 0.0), (1e4, R, 3.0, -4.0),
                  (1e9, 0.5 * R, 10.0, 10.0)):
            assert w.determinant(x) == pytest.approx(-1.0, rel=1e-12)

    def test_symmetric(self):
        w = create_alcubierre_metric(V, R, SIGMA)
        g = w.tensor((0.0, 60.0, 5.0, 0.0))
        for i in range(4):
            for j in range(4):
                assert g[i][j] == pytest.approx(g[j][i], rel=1e-14)

    def test_shape_function_bounds(self):
        w = create_alcubierre_metric(V, R, SIGMA)
        assert w.shape_function(0.0) == pytest.approx(1.0)
        # The wall is centered on r_s = R: top-hat midpoint there.
        assert abs(w.shape_function(R) - 0.5) < 0.01
        assert w.shape_function(50.0) == pytest.approx(1.0)   # deep interior
        assert w.shape_function(1e5) < 1e-9                    # far exterior

    def test_christoffels_finite_at_wall(self):
        w = create_alcubierre_metric(V, R, SIGMA)
        gamma = christoffel_symbols(w, (0.0, R, 0.0, 0.0))
        worst = max(abs(gamma[a][b][c]) for a in range(4) for b in range(4)
                    for c in range(4))
        assert math.isfinite(worst)


class TestLocalCausalityPreserved:
    # Inside a v_s = 5c bubble the interior floor is Minkowski in
    # X = x - v_s t: admissible massive worldlines need
    # dx/dt in (v_s - 1, v_s + 1) c. A dx/dt = 0 particle is SPACELIKE
    # there (it races across the floor at -5c) and MUST be rejected.

    def test_comoving_particle_normalization_exact(self):
        # The bubble-comoving geodesic: dx/dt = v_s c -> g(u,u) = -c^2.
        w = create_alcubierre_metric(V, R, SIGMA)
        ev = create_event(0.0, 0.0, 0.0, 0.0)
        coords, u = cartesian_state_to_chart(w, ev, Vector3(V * C, 0.0, 0.0))
        g = w.tensor(coords)
        norm = sum(g[a][b] * u[a] * u[b] for a in range(4) for b in range(4))
        assert norm == pytest.approx(-C * C, rel=1e-12)

    def test_interior_subluminal_worldline_allowed(self):
        # dx/dt = (v_s - 0.5) c: inside the interior light cone.
        w = create_alcubierre_metric(V, R, SIGMA)
        ev = create_event(0.0, 0.0, 0.0, 0.0)
        coords, u = cartesian_state_to_chart(w, ev, Vector3((V - 0.5) * C, 0.0, 0.0))
        g = w.tensor(coords)
        norm = sum(g[a][b] * u[a] * u[b] for a in range(4) for b in range(4))
        assert norm < 0.0  # timelike

    def test_interior_spacelike_worldline_rejected(self):
        # dx/dt = (v_s - 2) c: superluminal RELATIVE TO THE FLOOR (-2c).
        w = create_alcubierre_metric(V, R, SIGMA)
        ev = create_event(0.0, 0.0, 0.0, 0.0)
        from astra.relativity.exceptions import LightSpeedViolation
        with pytest.raises(LightSpeedViolation):
            cartesian_state_to_chart(w, ev, Vector3((V - 2.0) * C, 0.0, 0.0))

    def test_persistence_round_trip(self):
        w = create_alcubierre_metric(V, R, SIGMA)
        restored = type(w).from_dict(w.to_dict())
        x = (0.0, 60.0, 5.0, 0.0)
        assert restored.tensor(x) == w.tensor(x)
        assert restored.velocity == V and restored.radius_m == R
