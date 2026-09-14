import math
import pytest
from astra.mathematics.ode import euler_step, rk4_step, rk45_step, integrate

def exp_deriv(t, y):
    return (y[0],)

class TestFixedStep:
    def test_euler(self):
        y = (1.0,)
        y = euler_step(exp_deriv, 0.0, y, 0.01)
        assert y[0] == pytest.approx(1.01)
    def test_rk4_exp(self):
        y = (1.0,)
        for _ in range(100):
            y = rk4_step(exp_deriv, 0.0, y, 0.01)
        assert y[0] == pytest.approx(math.exp(1.0), abs=1e-8)
    def test_bad_h(self):
        with pytest.raises(ValueError):
            euler_step(exp_deriv, 0.0, (1.0,), -0.1)

class TestRK45:
    def test_rk45_step(self):
        y5, y4, err = rk45_step(exp_deriv, 0.0, (1.0,), 0.01)
        assert y5[0] == pytest.approx(math.exp(0.01), abs=1e-8)
        assert err >= 0.0

class TestIntegrate:
    def test_fixed(self):
        r = integrate(exp_deriv, 0.0, (1.0,), 1.0, h=0.001)
        assert r.y[0] == pytest.approx(math.exp(1.0), abs=1e-6)
        assert r.accepted > 0
    def test_adaptive(self):
        r = integrate(exp_deriv, 0.0, (1.0,), 1.0, h=0.1, adaptive=True)
        assert r.y[0] == pytest.approx(math.exp(1.0), abs=1e-6)
    def test_backward_rejected(self):
        with pytest.raises(ValueError):
            integrate(exp_deriv, 0.0, (1.0,), -1.0, h=0.1)
    def test_bad_h(self):
        with pytest.raises(ValueError):
            integrate(exp_deriv, 0.0, (1.0,), 1.0, h=0.0)
    def test_harmonic_oscillator(self):
        def deriv(t, y):
            x, v = y
            return (v, -x)
        r = integrate(deriv, 0.0, (1.0, 0.0), math.tau, h=0.001)
        assert r.y[0] == pytest.approx(1.0, abs=1e-3)
        assert r.y[1] == pytest.approx(0.0, abs=1e-3)
