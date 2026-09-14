import math
import pytest
from astra.spacecraft import (
    rocket_delta_v, propellant_for_delta_v, remaining_delta_v,
    mass_after_delta_v, G0,
    InvalidRocketEquationError,
)


class TestRocketEquation:
    def test_known_value(self):
        # Isp=300, m0=1000, mf=500 -> dv = 300*9.80665*ln(2) ~ 2038.7
        dv = rocket_delta_v(1000.0, 500.0, 300.0)
        assert dv == pytest.approx(300.0 * G0 * math.log(2.0))

    def test_zero_propellant(self):
        assert rocket_delta_v(1000.0, 1000.0, 300.0) == 0.0

    def test_final_greater_than_initial(self):
        with pytest.raises(InvalidRocketEquationError):
            rocket_delta_v(500.0, 1000.0, 300.0)

    def test_zero_isp(self):
        with pytest.raises(InvalidRocketEquationError):
            rocket_delta_v(1000.0, 500.0, 0.0)

    def test_negative_isp(self):
        with pytest.raises(InvalidRocketEquationError):
            rocket_delta_v(1000.0, 500.0, -100.0)

    def test_nan_isp(self):
        with pytest.raises(InvalidRocketEquationError):
            rocket_delta_v(1000.0, 500.0, float("nan"))


class TestPropellantForDeltaV:
    def test_roundtrip(self):
        m0 = 1000.0
        dv = 500.0
        isp = 300.0
        prop = propellant_for_delta_v(m0, dv, isp)
        mf = m0 - prop
        dv2 = rocket_delta_v(m0, mf, isp)
        assert dv2 == pytest.approx(dv, rel=1e-9)

    def test_zero_dv_no_propellant(self):
        assert propellant_for_delta_v(1000.0, 0.0, 300.0) == 0.0


class TestMassAfterDeltaV:
    def test_consistent_with_propellant(self):
        m0 = 1000.0
        dv = 500.0
        isp = 300.0
        mf = mass_after_delta_v(m0, dv, isp)
        prop = propellant_for_delta_v(m0, dv, isp)
        assert m0 - mf == pytest.approx(prop)


class TestRemainingDeltaV:
    def test_full_tank(self):
        # m_current = 1000, m_dry = 100, Isp = 300
        dv = remaining_delta_v(1000.0, 100.0, 300.0)
        assert dv == pytest.approx(300.0 * G0 * math.log(10.0))

    def test_empty_tank(self):
        assert remaining_delta_v(100.0, 100.0, 300.0) == 0.0

    def test_invalid_m_dry(self):
        with pytest.raises(InvalidRocketEquationError):
            remaining_delta_v(1000.0, 2000.0, 300.0)
