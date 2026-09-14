"""Adversarial Black-Hole tests: NaN/Inf attacks, naked singularities,
horizon-precision attacks, extremal-spin stability, determinism."""
import math

import pytest

from astra.core.exceptions import AstraError
from astra.blackhole import (
    BlackHoleError,
    CoordinateSingularityError,
    InvalidBlackHoleMassError,
    InvalidGeometryInputError,
    InvalidSpinParameterError,
    calculate_ergosphere_radius,
    create_black_hole,
    equatorial_frame_dragging_velocity,
    gravitational_redshift,
    gravitational_time_dilation,
    kerr,
    schwarzschild,
)

MASS_SUN = 1.989e30  # kg


class TestMaliciousInputs:
    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    def test_nan_inf_mass_rejected(self, bad):
        with pytest.raises(InvalidBlackHoleMassError):
            create_black_hole(bad)

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    def test_nan_inf_spin_rejected(self, bad):
        with pytest.raises(InvalidSpinParameterError):
            create_black_hole(MASS_SUN, bad)

    def test_over_spin_no_float_bypass(self):
        # P2 regression: nothing between 1.0 and 1 + k*ulp may slip through.
        with pytest.raises(InvalidSpinParameterError):
            create_black_hole(MASS_SUN, math.nextafter(1.0, math.inf))

    def test_error_hierarchy(self):
        assert issubclass(BlackHoleError, AstraError)
        assert issubclass(CoordinateSingularityError, BlackHoleError)
        assert issubclass(InvalidGeometryInputError, BlackHoleError)

    def test_non_numeric_geometry_rejected(self):
        bh = create_black_hole(MASS_SUN)
        with pytest.raises(InvalidGeometryInputError):
            gravitational_time_dilation(bh, "10 km")
        with pytest.raises(InvalidGeometryInputError):
            calculate_ergosphere_radius(bh, float("nan"))


class TestHorizonPrecisionAttacks:
    def test_physical_singularity_r_zero(self):
        bh = create_black_hole(MASS_SUN)
        with pytest.raises(CoordinateSingularityError):
            gravitational_time_dilation(bh, 0.0)

    def test_epsilon_band_blocked(self):
        bh = create_black_hole(MASS_SUN)
        rs = schwarzschild.schwarzschild_radius_m(MASS_SUN)
        for r in (rs, math.nextafter(rs, math.inf), rs + 1e-10, rs + 1e-9):
            with pytest.raises(CoordinateSingularityError):
                gravitational_time_dilation(bh, r)

    def test_first_allowed_radius_beyond_epsilon_works(self):
        bh = create_black_hole(MASS_SUN)
        rs = schwarzschild.schwarzschild_radius_m(MASS_SUN)
        # Just past the guard: finite, > 1, no exceptions.
        value = gravitational_time_dilation(bh, rs + 2e-9)
        assert math.isfinite(value) and value > 1.0

    def test_redshift_domain_attack_blocked(self):
        # P1 regression: emitter infinitesimally above r_s previously risked
        # ValueError: math domain error. The epsilon guard must intercept it.
        bh = create_black_hole(MASS_SUN)
        rs = schwarzschild.schwarzschild_radius_m(MASS_SUN)
        for r_em in (
            math.nextafter(rs, math.inf),
            rs * (1.0 + 1e-15),
            rs + 5e-10,
        ):
            with pytest.raises(CoordinateSingularityError):
                gravitational_redshift(bh, r_em, 1e12 * rs)

    def test_kerr_horizon_band_blocked(self):
        bh = create_black_hole(MASS_SUN, 0.9)
        r_plus, _ = kerr.horizons(bh)
        for r in (r_plus, r_plus + 1e-10, r_plus * 0.999):
            with pytest.raises(CoordinateSingularityError):
                equatorial_frame_dragging_velocity(bh, r)


class TestExtremalStability:
    def test_extremal_horizons_no_complex_no_crash(self):
        # Regression: cancellation drift must not yield negative discriminant.
        for a in (1.0, -1.0, math.nextafter(1.0, 0.0)):
            bh = create_black_hole(MASS_SUN, a)
            r_plus, r_minus = kerr.horizons(bh)
            rg = bh.gravitational_radius
            assert math.isfinite(r_plus) and math.isfinite(r_minus)
            assert abs(r_plus - rg) <= 1e-6 * rg
            assert r_minus <= r_plus

    def test_extremal_ergosphere_finite(self):
        bh = create_black_hole(MASS_SUN, 1.0)
        for theta in (0.0, math.pi / 4, math.pi / 2, math.pi):
            assert math.isfinite(kerr.ergosphere_radius(bh, theta))

    def test_extremal_isco_finite(self):
        bh = create_black_hole(MASS_SUN, 1.0)
        assert math.isfinite(kerr.isco_prograde(bh))
        assert math.isfinite(kerr.isco_retrograde(bh))

    def test_near_extremal_spin_stability(self):
        a_star = 1.0 - 1e-13
        bh = create_black_hole(MASS_SUN, a_star)
        r_plus, r_minus = kerr.horizons(bh)
        rg = bh.gravitational_radius
        # Analytic: 1 - a*^2 ~ 2e-13 -> sqrt = 4.5e-7, so r+ = rg(1 + 4.5e-7).
        expected = rg * (1.0 + math.sqrt(1.0 - a_star * a_star))
        assert r_plus == pytest.approx(expected, rel=1e-9)
        assert r_plus < rg * (1.0 + 1e-6)


class TestFacadeDispatch:
    def test_ergosphere_defined_for_schwarzschild(self):
        bh = create_black_hole(MASS_SUN, 0.0)
        rs = schwarzschild.schwarzschild_radius_m(MASS_SUN)
        assert calculate_ergosphere_radius(bh, 0.0) == pytest.approx(rs, rel=1e-14)
        assert calculate_ergosphere_radius(bh, math.pi / 2) == pytest.approx(rs, rel=1e-14)

    def test_facade_matches_kerr_subsystem(self):
        bh = create_black_hole(MASS_SUN, 0.6)
        r = 5.0 * bh.gravitational_radius
        assert gravitational_time_dilation(bh, r) == (
            kerr.static_time_dilation_equatorial(bh, r)
        )

    def test_redshift_kerr_equals_schwarzschild_equatorial(self):
        pos = create_black_hole(MASS_SUN, 0.6)
        zero = create_black_hole(MASS_SUN, 0.0)
        rg = pos.gravitational_radius
        z_kerr = gravitational_redshift(pos, 3.0 * rg, 50.0 * rg)
        z_schw = gravitational_redshift(zero, 3.0 * rg, 50.0 * rg)
        assert z_kerr == pytest.approx(z_schw, rel=1e-14)


class TestDeterminism:
    def test_five_thousand_identical_evaluations(self):
        # Contract (handoff section 17): 5000 identical runs must produce
        # bit-for-bit identical floating-point outputs.
        bh = create_black_hole(MASS_SUN, 0.75)
        rg = bh.gravitational_radius

        def snapshot():
            return (
                kerr.horizons(bh),
                kerr.ergosphere_radius(bh, math.pi / 4),
                kerr.isco_prograde(bh),
                kerr.isco_retrograde(bh),
                kerr.frame_dragging_angular_velocity(bh, 10.0 * rg),
                gravitational_time_dilation(bh, 10.0 * rg),
                gravitational_redshift(bh, 3.0 * rg, 100.0 * rg),
                schwarzschild.schwarzschild_radius_m(MASS_SUN),
            )

        first = snapshot()
        for _ in range(5000):
            assert snapshot() == first
