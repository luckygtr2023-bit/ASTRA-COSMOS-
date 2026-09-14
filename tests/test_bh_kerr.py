"""Kerr subsystem tests: horizons, ergosphere, frame dragging, ISCO,
photon orbits, extremal limits - checked against published reference values."""
import math

import pytest

from astra.blackhole import (
    BlackHoleModel,
    CoordinateSingularityError,
    create_black_hole,
    get_kerr_boundaries,
    kerr,
    schwarzschild,
)

MASS_SUN = 1.989e30  # kg


class TestHorizons:
    def test_zero_spin_recovers_schwarzschild(self):
        bh = create_black_hole(MASS_SUN)
        r_plus, r_minus = kerr.horizons(bh)
        rs = schwarzschild.schwarzschild_radius_m(MASS_SUN)
        assert r_plus == pytest.approx(rs, rel=1e-14)
        assert r_minus == 0.0

    def test_extremal_horizons_degenerate(self):
        bh = create_black_hole(MASS_SUN, 1.0)
        r_plus, r_minus = kerr.horizons(bh)
        assert r_plus == pytest.approx(bh.gravitational_radius, rel=1e-12)
        assert r_minus == pytest.approx(r_plus, rel=1e-12)

    def test_horizons_straddle_with_spin(self):
        bh = create_black_hole(MASS_SUN, 0.5)
        r_plus, r_minus = kerr.horizons(bh)
        rg = bh.gravitational_radius
        assert r_minus < r_plus
        assert r_plus > rg and r_plus < 2.0 * rg
        assert 0.0 < r_minus < rg

    def test_horizon_symmetric_in_spin_sign(self):
        pos = kerr.horizons(create_black_hole(MASS_SUN, 0.6))
        neg = kerr.horizons(create_black_hole(MASS_SUN, -0.6))
        assert pos[0] == pytest.approx(neg[0], rel=1e-15)
        assert pos[1] == pytest.approx(neg[1], rel=1e-15)


class TestErgosphere:
    def test_touches_horizon_at_poles(self):
        bh = create_black_hole(MASS_SUN, 0.5)
        r_plus, _ = kerr.horizons(bh)
        assert kerr.ergosphere_radius(bh, 0.0) == pytest.approx(r_plus, rel=1e-12)
        assert kerr.ergosphere_radius(bh, math.pi) == pytest.approx(r_plus, rel=1e-12)

    def test_equator_is_two_gravitational_radii(self):
        # r_E(pi/2) = r_g + sqrt(r_g^2 - 0) = 2 r_g, independent of spin.
        for a in (0.0, 0.3, 0.9, 1.0):
            bh = create_black_hole(MASS_SUN, a)
            assert kerr.ergosphere_radius(bh, math.pi / 2) == pytest.approx(
                2.0 * bh.gravitational_radius, rel=1e-14
            )

    def test_ergosphere_between_horizon_and_equator(self):
        bh = create_black_hole(MASS_SUN, 0.5)
        r_plus, _ = kerr.horizons(bh)
        ergo_eq = 2.0 * bh.gravitational_radius
        for theta in (math.pi / 6, math.pi / 4, math.pi / 3):
            r_e = kerr.ergosphere_radius(bh, theta)
            assert r_plus <= r_e <= ergo_eq

    def test_schwarzschild_ergosphere_constant(self):
        bh = create_black_hole(MASS_SUN, 0.0)
        for theta in (0.0, 0.7, math.pi / 2, 2.4):
            assert kerr.ergosphere_radius(bh, theta) == pytest.approx(
                schwarzschild.schwarzschild_radius_m(MASS_SUN), rel=1e-14
            )


class TestISCO:
    def test_zero_spin_six_gravitational_radii(self):
        bh = create_black_hole(MASS_SUN)
        assert kerr.isco_prograde(bh) == pytest.approx(
            schwarzschild.isco_radius(MASS_SUN), rel=1e-14
        )

    def test_extremal_limits(self):
        bh = create_black_hole(MASS_SUN, 1.0)
        assert kerr.isco_prograde(bh) == pytest.approx(bh.gravitational_radius, rel=1e-9)
        assert kerr.isco_retrograde(bh) == pytest.approx(9.0 * bh.gravitational_radius, rel=1e-9)

    def test_reference_value_half_spin(self):
        # Published BPT value: a*=0.5 -> 4.2330 r_g (prograde).
        bh = create_black_hole(MASS_SUN, 0.5)
        assert kerr.isco_prograde(bh) / bh.gravitational_radius == pytest.approx(4.2330, abs=1e-3)

    def test_retrograde_never_inside_prograde(self):
        for a in (0.1, 0.5, 0.9, 1.0):
            bh = create_black_hole(MASS_SUN, a)
            assert kerr.isco_retrograde(bh) > kerr.isco_prograde(bh)

    def test_spin_deepens_prograde_isco(self):
        rg = None
        prev = None
        for a in (0.0, 0.25, 0.5, 0.75, 1.0):
            bh = create_black_hole(MASS_SUN, a)
            r = kerr.isco_prograde(bh)
            if prev is not None:
                assert r < prev
            prev = r


class TestPhotonOrbits:
    def test_zero_spin_three_radii(self):
        bh = create_black_hole(MASS_SUN)
        assert kerr.photon_orbit_prograde(bh) == pytest.approx(
            schwarzschild.photon_sphere_radius(MASS_SUN), rel=1e-14
        )

    def test_extremal_limits(self):
        bh = create_black_hole(MASS_SUN, 1.0)
        assert kerr.photon_orbit_prograde(bh) == pytest.approx(bh.gravitational_radius, rel=1e-12)
        assert kerr.photon_orbit_retrograde(bh) == pytest.approx(
            4.0 * bh.gravitational_radius, rel=1e-12
        )

    def test_prograde_inside_retrograde(self):
        bh = create_black_hole(MASS_SUN, 0.5)
        assert kerr.photon_orbit_prograde(bh) < kerr.photon_orbit_retrograde(bh)


class TestFrameDragging:
    def test_zero_spin_zero_dragging(self):
        bh = create_black_hole(MASS_SUN, 0.0)
        r = 10.0 * bh.gravitational_radius
        assert kerr.frame_dragging_angular_velocity(bh, r) == 0.0

    def test_sign_follows_spin(self):
        bh_pos = create_black_hole(MASS_SUN, 0.5)
        r = 10.0 * bh_pos.gravitational_radius  # safely outside the horizon
        pos = kerr.frame_dragging_angular_velocity(bh_pos, r)
        neg = kerr.frame_dragging_angular_velocity(create_black_hole(MASS_SUN, -0.5), r)
        assert pos > 0.0 and neg < 0.0
        assert pos == pytest.approx(-neg, rel=1e-14)

    def test_increases_toward_horizon(self):
        bh = create_black_hole(MASS_SUN, 0.5)
        r_plus, _ = kerr.horizons(bh)
        w_far = kerr.frame_dragging_angular_velocity(bh, 50.0 * bh.gravitational_radius)
        w_near = kerr.frame_dragging_angular_velocity(bh, r_plus * 1.001)
        assert w_near > w_far > 0.0

    def test_at_horizon_raises(self):
        bh = create_black_hole(MASS_SUN, 0.5)
        r_plus, _ = kerr.horizons(bh)
        with pytest.raises(CoordinateSingularityError):
            kerr.frame_dragging_angular_velocity(bh, r_plus)

    def test_facade_velocity_zero_for_schwarzschild(self):
        from astra.blackhole import equatorial_frame_dragging_velocity
        bh = create_black_hole(MASS_SUN, 0.0)
        assert equatorial_frame_dragging_velocity(bh, 100.0) == 0.0

    def test_facade_velocity_positive_for_kerr(self):
        from astra.blackhole import equatorial_frame_dragging_velocity
        bh = create_black_hole(MASS_SUN, 0.5)
        r = 10.0 * bh.gravitational_radius
        v = equatorial_frame_dragging_velocity(bh, r)
        assert v == pytest.approx(
            kerr.frame_dragging_angular_velocity(bh, r) * r, rel=1e-15
        )


class TestKerrTimeDilation:
    def test_zero_spin_matches_schwarzschild_outside_ergosphere(self):
        bh = create_black_hole(MASS_SUN, 0.5)
        r = 4.0 * bh.gravitational_radius  # outside 2 r_g ergosphere
        expected = 1.0 / math.sqrt(1.0 - 2.0 * bh.gravitational_radius / r)
        assert kerr.static_time_dilation_equatorial(bh, r) == pytest.approx(expected, rel=1e-14)

    def test_inside_ergosphere_raises(self):
        bh = create_black_hole(MASS_SUN, 0.5)
        with pytest.raises(CoordinateSingularityError):
            kerr.static_time_dilation_equatorial(bh, 1.5 * bh.gravitational_radius)


class TestFacadeKerrBoundaries:
    def test_boundaries_dict_consistent(self):
        bh = create_black_hole(MASS_SUN, 0.7)
        b = get_kerr_boundaries(bh)
        assert b["r_plus"] > b["r_minus"] > 0.0
        assert b["ergosphere_equatorial"] >= b["r_plus"]
        assert b["ergosphere_polar"] == pytest.approx(b["r_plus"], rel=1e-12)
        assert b["isco_prograde"] < b["isco_retrograde"]
        assert b["photon_orbit_prograde"] < b["photon_orbit_retrograde"]
