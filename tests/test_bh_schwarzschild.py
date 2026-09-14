"""Schwarzschild subsystem tests: exact geometric relations and continuity
with the astra.relativity foundations."""
import math

import pytest

from astra.blackhole import (
    CoordinateSingularityError,
    create_black_hole,
    get_schwarzschild_boundaries,
    gravitational_redshift,
    gravitational_time_dilation,
    schwarzschild,
)
from astra.relativity.gr_foundations import (
    schwarzschild_radius as relativity_schwarzschild_radius,
    weak_field_time_dilation as relativity_time_dilation,
)

MASS_SUN = 1.989e30      # kg
MASS_EARTH = 5.972e24    # kg


class TestRadii:
    def test_schwarzschild_radius_earth(self):
        rs = schwarzschild.schwarzschild_radius_m(MASS_EARTH)
        assert 0.008 < rs < 0.009  # ~8.87 mm

    def test_schwarzschild_radius_sun(self):
        rs = schwarzschild.schwarzschild_radius_m(MASS_SUN)
        assert 2953.0 < rs < 2955.0  # ~2.95 km

    def test_continuity_with_relativity_layer(self):
        # Contract: identical formula, single implementation family.
        assert schwarzschild.schwarzschild_radius_m(MASS_SUN) == (
            relativity_schwarzschild_radius(MASS_SUN)
        )

    def test_isco_is_three_schwarzschild_radii(self):
        rs = schwarzschild.schwarzschild_radius_m(MASS_SUN)
        assert schwarzschild.isco_radius(MASS_SUN) == pytest.approx(3.0 * rs, rel=1e-15)

    def test_photon_sphere_is_one_and_a_half_radii(self):
        rs = schwarzschild.schwarzschild_radius_m(MASS_SUN)
        assert schwarzschild.photon_sphere_radius(MASS_SUN) == pytest.approx(1.5 * rs, rel=1e-15)

    def test_scales_linearly_with_mass(self):
        assert schwarzschild.schwarzschild_radius_m(2.0 * MASS_SUN) == (
            pytest.approx(2.0 * schwarzschild.schwarzschild_radius_m(MASS_SUN), rel=1e-15)
        )


class TestTimeDilation:
    def test_continuity_with_relativity_layer(self):
        bh = create_black_hole(MASS_EARTH)
        r = 6371000.0
        assert gravitational_time_dilation(bh, r) == (
            relativity_time_dilation(MASS_EARTH, r)
        )

    def test_closed_form_at_ten_radii(self):
        bh = create_black_hole(MASS_SUN)
        rs = schwarzschild.schwarzschild_radius_m(MASS_SUN)
        expected = 1.0 / math.sqrt(1.0 - 0.1)
        assert gravitational_time_dilation(bh, 10.0 * rs) == pytest.approx(expected, rel=1e-14)

    def test_dilation_increases_toward_horizon(self):
        bh = create_black_hole(MASS_SUN)
        rs = schwarzschild.schwarzschild_radius_m(MASS_SUN)
        near = gravitational_time_dilation(bh, 1.001 * rs)
        far = gravitational_time_dilation(bh, 100.0 * rs)
        assert near > far > 1.0

    def test_at_horizon_raises(self):
        bh = create_black_hole(MASS_SUN)
        rs = schwarzschild.schwarzschild_radius_m(MASS_SUN)
        for r in (rs, rs * 0.5, rs + 5e-10):  # at, inside, and within epsilon
            with pytest.raises(CoordinateSingularityError):
                gravitational_time_dilation(bh, r)


class TestRedshift:
    def test_equal_radii_zero_redshift(self):
        bh = create_black_hole(MASS_SUN)
        rs = schwarzschild.schwarzschild_radius_m(MASS_SUN)
        assert gravitational_redshift(bh, 5.0 * rs, 5.0 * rs) == 0.0

    def test_emitter_at_two_radii_infinity_observer(self):
        # z = sqrt(1 / (1 - r_s/r_em)) - 1 = sqrt(2) - 1 for r_em = 2 r_s.
        bh = create_black_hole(MASS_SUN)
        rs = schwarzschild.schwarzschild_radius_m(MASS_SUN)
        z = gravitational_redshift(bh, 2.0 * rs, 1e12 * rs)
        assert z == pytest.approx(math.sqrt(2.0) - 1.0, rel=1e-12)

    def test_redshift_grows_near_horizon(self):
        bh = create_black_hole(MASS_SUN)
        rs = schwarzschild.schwarzschild_radius_m(MASS_SUN)
        z_outer = gravitational_redshift(bh, 10.0 * rs, 1e12 * rs)
        z_inner = gravitational_redshift(bh, 1.000000001 * rs, 1e12 * rs)
        assert z_inner > z_outer > 0.0

    def test_blueshift_for_deeper_observer(self):
        bh = create_black_hole(MASS_SUN)
        rs = schwarzschild.schwarzschild_radius_m(MASS_SUN)
        assert gravitational_redshift(bh, 10.0 * rs, 5.0 * rs) < 0.0

    def test_emitter_inside_horizon_raises(self):
        bh = create_black_hole(MASS_SUN)
        rs = schwarzschild.schwarzschild_radius_m(MASS_SUN)
        with pytest.raises(CoordinateSingularityError):
            gravitational_redshift(bh, rs * 0.9, 100.0 * rs)


class TestFacadeBoundaries:
    def test_boundaries_dict(self):
        bh = create_black_hole(MASS_SUN)
        b = get_schwarzschild_boundaries(bh)
        assert b["isco_radius"] == pytest.approx(3.0 * b["schwarzschild_radius"], rel=1e-15)
        assert b["photon_sphere_radius"] == pytest.approx(
            1.5 * b["schwarzschild_radius"], rel=1e-15
        )
        assert b["gravitational_radius"] == pytest.approx(
            0.5 * b["schwarzschild_radius"], rel=1e-15
        )
