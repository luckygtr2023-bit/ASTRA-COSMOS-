import math
import pytest
from astra.orbital import (
    plane_change_delta_v, circularize_delta_v,
    hohmann_transfer, bielliptic_transfer,
    HohmannTransfer, BiellipticTransfer,
    synodic_period, phase_angle_for_rendezvous,
    orbital_period, circular_velocity,
    InvalidTransferError, InvalidOrbitError,
)


MU_EARTH = 3.986004418e14
MU_SUN = 1.32712440018e20


class TestPlaneChange:
    def test_pure_inclination_change(self):
        v = 7670.0
        dv = plane_change_delta_v(v, math.radians(28.5))
        expected = 2.0 * v * math.sin(math.radians(28.5) / 2.0)
        assert abs(dv - expected) < 1e-9

    def test_zero_change(self):
        assert plane_change_delta_v(7670.0, 0.0) == 0.0

    def test_pi_change(self):
        v = 7670.0
        assert plane_change_delta_v(v, math.pi) == pytest.approx(2.0 * v, rel=1e-12)


class TestHohmann:
    def test_leo_to_geo(self):
        r1 = 6.678e6       # LEO
        r2 = 4.2164e7      # GEO
        h = hohmann_transfer(r1, r2, MU_EARTH)
        assert isinstance(h, HohmannTransfer)
        assert h.delta_v_1 > 0.0
        assert h.delta_v_2 > 0.0
        assert h.total_delta_v == pytest.approx(h.delta_v_1 + h.delta_v_2, rel=1e-12)
        # Known LEO->GEO Hohmann ~ 3.9 km/s
        assert 3800.0 < h.total_delta_v < 4000.0

    def test_transfer_time_half_period(self):
        r1, r2 = 7.0e6, 4.2e7
        h = hohmann_transfer(r1, r2, MU_EARTH)
        expected_t = 0.5 * orbital_period(0.5 * (r1 + r2), MU_EARTH)
        assert abs(h.transfer_time - expected_t) < 1e-3

    def test_symmetric_dv(self):
        r1, r2 = 7.0e6, 4.2e7
        h_out = hohmann_transfer(r1, r2, MU_EARTH)
        h_in = hohmann_transfer(r2, r1, MU_EARTH)
        assert abs(h_out.total_delta_v - h_in.total_delta_v) < 1e-6

    def test_invalid_radius(self):
        with pytest.raises(InvalidTransferError):
            hohmann_transfer(0.0, 1e7, MU_EARTH)
        with pytest.raises(InvalidTransferError):
            hohmann_transfer(1e7, -1.0, MU_EARTH)


class TestBielliptic:
    def test_far_transfer_better_than_hohmann(self):
        # r2/r1 ~ 20, rb far out
        r1 = 1.0e7
        r2 = 2.0e8
        rb = 1.0e9
        b = bielliptic_transfer(r1, r2, rb, MU_EARTH)
        h = hohmann_transfer(r1, r2, MU_EARTH)
        assert b.total_delta_v < h.total_delta_v

    def test_near_transfer_worse(self):
        r1 = 7.0e6
        r2 = 1.5e7
        rb = 2.0e7
        b = bielliptic_transfer(r1, r2, rb, MU_EARTH)
        h = hohmann_transfer(r1, r2, MU_EARTH)
        assert b.total_delta_v > h.total_delta_v

    def test_invalid_rb(self):
        with pytest.raises(InvalidTransferError):
            bielliptic_transfer(7.0e6, 1.0e8, 5.0e6, MU_EARTH)


class TestWindows:
    def test_synodic_earth_mars(self):
        # Approx: T_earth = 365.25 d, T_mars = 686.98 d
        T_e = 365.25 * 86400.0
        T_m = 686.98 * 86400.0
        Ts = synodic_period(T_e, T_m)
        Ts_days = Ts / 86400.0
        assert 770.0 < Ts_days < 790.0

    def test_synodic_identical_periods_raises(self):
        with pytest.raises(InvalidOrbitError):
            synodic_period(100.0, 100.0)

    def test_phase_angle_hohmann(self):
        # Hohmann transfer to a body at 1.524 AU, T_target ~ 687 d
        T_target = 686.98 * 86400.0
        # Transfer time for Earth->Mars Hohmann
        a_t = 0.5 * (1.0 + 1.524) * 1.496e11
        t_transfer = 0.5 * 2.0 * math.pi * math.sqrt(a_t ** 3 / MU_SUN)
        phi = phase_angle_for_rendezvous(T_target, t_transfer)
        # Expected phase angle ~ 44 degrees
        phi_deg = math.degrees(phi)
        assert 40.0 < phi_deg < 50.0
