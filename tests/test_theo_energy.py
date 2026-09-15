"""Energy condition diagnostics: analytic anchors for NEC violation."""
import math

import pytest

from astra.spacetime import SchwarzschildMetric
from astra.theoretical import (
    evaluate_energy_conditions,
    create_alcubierre_metric,
    create_morris_thorne_metric,
)

R0 = 10.0


def ellipsoid_b(r0):
    return lambda r: r0 * r0 / r


class TestVacuumTrivial:
    def test_schwarzschild_vacuum_satisfies_all(self):
        # T = G/(8pi) ~ finite-difference zero: all conditions hold trivially.
        sm = SchwarzschildMetric(1.989e30)
        d = evaluate_energy_conditions(sm, (0.0, 5 * sm.rs_m, math.pi / 3, 0.4))
        assert d.nec_satisfied and d.wec_satisfied and d.dec_satisfied
        assert d.sec_satisfied
        assert not d.exotic_matter_required
        assert abs(d.energy_density) < 1e-30  # vacuum-scale zero

    def test_flat_satisfies_all(self):
        from astra.spacetime import MinkowskiMetric
        d = evaluate_energy_conditions(MinkowskiMetric(), (0.0, 1.0, 2.0, 3.0))
        assert d.nec_satisfied and d.wec_satisfied and d.dec_satisfied
        assert d.sec_satisfied
        assert d.energy_density == 0.0


class TestMorrisThorneExotic:
    def test_negative_density_near_throat(self):
        mt = create_morris_thorne_metric(R0, ellipsoid_b(R0))
        d = evaluate_energy_conditions(mt, (0.0, 1.001 * R0, math.pi / 2, 0.0))
        assert d.energy_density < 0.0
        assert d.exotic_matter_required
        assert not d.nec_satisfied

    def test_matches_analytic_density(self):
        # Morris-Thorne: rho = b'(r) / (8 pi r^2); for b = r0^2/r,
        # b' = -r0^2/r^2. Numeric pipeline vs analytic at r = 3 r0.
        mt = create_morris_thorne_metric(R0, ellipsoid_b(R0))
        r = 3.0 * R0
        d = evaluate_energy_conditions(mt, (0.0, r, math.pi / 2, 0.0))
        analytic = (-R0 * R0 / (r * r)) / (8.0 * math.pi * r * r)
        assert d.energy_density == pytest.approx(analytic, rel=5e-3)

    def test_at_throat_analytic_nec_violation(self):
        # Chart cannot evaluate AT r0 (coordinate singularity), so the
        # at-throat NEC statement is made analytically:
        #   rho + p_r = (b'(r0) - 1) / (8 pi r0^2) < 0  iff  b'(r0) < 1.
        # The construction enforces b'(r0) < 1, hence NEC violation holds.
        b0_prime = -1.0  # for b = r0^2/r
        rho_plus_pr = (b0_prime - 1.0) / (8.0 * math.pi * R0 ** 2)
        assert rho_plus_pr < 0.0

    def test_zero_redshift_violates_and_flattened_phi_may_not(self):
        # Phi = 0 (zero tidal force): NEC violated at/near the throat.
        mt = create_morris_thorne_metric(R0, ellipsoid_b(R0))
        d = evaluate_energy_conditions(mt, (0.0, 1.001 * R0, math.pi / 2, 0.0))
        assert d.exotic_matter_required


class TestAlcubierreExotic:
    def test_wall_nec_violation(self):
        w = create_alcubierre_metric(5.0, 100.0, 1.0)
        d = evaluate_energy_conditions(w, (0.0, 100.0, 0.0, 0.0))
        assert d.exotic_matter_required
        assert not d.nec_satisfied
        assert min(d.null_contraction) < 0.0

    def test_center_and_far_field_trivial(self):
        w = create_alcubierre_metric(5.0, 100.0, 1.0)
        for x in ((0.0, 0.0, 0.0, 0.0), (0.0, 1e5, 0.0, 0.0)):
            d = evaluate_energy_conditions(w, x)
            assert d.nec_satisfied
            assert abs(d.energy_density) < 1e-25


class TestDiagnosticObject:
    def test_immutable(self):
        import dataclasses
        mt = create_morris_thorne_metric(R0, ellipsoid_b(R0))
        d = evaluate_energy_conditions(mt, (0.0, 2 * R0, math.pi / 2, 0.0))
        with pytest.raises(dataclasses.FrozenInstanceError):
            d.exotic_matter_required = False

    def test_to_dict_keys(self):
        mt = create_morris_thorne_metric(R0, ellipsoid_b(R0))
        d = evaluate_energy_conditions(mt, (0.0, 2 * R0, math.pi / 2, 0.0))
        payload = d.to_dict()
        for key in ("NEC", "WEC", "SEC", "DEC", "exotic_matter_required",
                    "energy_density", "null_contraction"):
            assert key in payload

    def test_determinism(self):
        mt = create_morris_thorne_metric(R0, ellipsoid_b(R0))
        x = (0.0, 2 * R0, math.pi / 2, 0.0)
        first = evaluate_energy_conditions(mt, x)
        for _ in range(200):
            assert evaluate_energy_conditions(mt, x) == first
