import math
import pytest
from astra.mathematics.numerical import (
    derivative_central, derivative_forward, derivative_backward,
    trapezoidal, simpson,
    bisection, newton_raphson, secant,
)

class TestDerivative:
    def test_central_sin(self):
        d = derivative_central(math.sin, 0.5)
        assert d == pytest.approx(math.cos(0.5), abs=1e-6)
    def test_forward(self):
        d = derivative_forward(math.sin, 0.5, h=1e-7)
        assert d == pytest.approx(math.cos(0.5), abs=1e-5)
    def test_backward(self):
        d = derivative_backward(math.sin, 0.5, h=1e-7)
        assert d == pytest.approx(math.cos(0.5), abs=1e-5)
    def test_bad_h(self):
        with pytest.raises(ValueError):
            derivative_central(math.sin, 0.5, h=-1.0)

class TestIntegration:
    def test_trapezoid_poly(self):
        v = trapezoidal(lambda x: x * x, 0, 1, n=1000)
        assert v == pytest.approx(1.0 / 3.0, abs=1e-4)
    def test_simpson_poly(self):
        v = simpson(lambda x: x * x, 0, 1, n=1000)
        assert v == pytest.approx(1.0 / 3.0, abs=1e-10)
    def test_simpson_requires_even(self):
        with pytest.raises(ValueError):
            simpson(lambda x: x, 0, 1, n=3)
    def test_empty_interval(self):
        assert trapezoidal(math.sin, 1, 1) == 0.0
        assert simpson(math.sin, 1, 1) == 0.0

class TestBisection:
    def test_sqrt2(self):
        r = bisection(lambda x: x * x - 2, 0, 2)
        assert r.converged
        assert r.root == pytest.approx(math.sqrt(2), abs=1e-9)
    def test_bad_bracket(self):
        with pytest.raises(ValueError):
            bisection(lambda x: x * x - 2, 2, 3)

class TestNewton:
    def test_sqrt2(self):
        r = newton_raphson(lambda x: x * x - 2, lambda x: 2 * x, 1.0)
        assert r.converged
        assert r.root == pytest.approx(math.sqrt(2), abs=1e-9)
    def test_zero_derivative(self):
        r = newton_raphson(lambda x: 1.0, lambda x: 0.0, 0.0)
        assert not r.converged
    def test_no_df(self):
        r = newton_raphson(lambda x: x * x - 2, None, 1.0)
        assert r.converged

class TestSecant:
    def test_sqrt2(self):
        r = secant(lambda x: x * x - 2, 1.0, 2.0)
        assert r.converged
        assert r.root == pytest.approx(math.sqrt(2), abs=1e-9)
