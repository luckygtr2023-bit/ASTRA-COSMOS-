import math
import pytest
from astra.mathematics.precision import (
    is_close, is_close_zero, is_finite, is_nan, is_inf,
    require_finite, safe_divide, clamp, clamp01, sign,
)

class TestIsClose:
    def test_exact(self):
        assert is_close(1.0, 1.0)
        assert is_close(0.0, 0.0)
    def test_near(self):
        assert is_close(1.0, 1.0 + 1e-13)
        assert is_close(1e6, 1e6 + 1e-3)
    def test_far(self):
        assert not is_close(1.0, 2.0)
    def test_nan(self):
        assert not is_close(float("nan"), float("nan"))
        assert not is_close(float("nan"), 1.0)
    def test_inf(self):
        assert is_close(float("inf"), float("inf"))
        assert is_close(float("-inf"), float("-inf"))
        assert not is_close(float("inf"), float("-inf"))
        assert not is_close(float("inf"), 1.0)

class TestCloseZero:
    def test_close_zero(self):
        assert is_close_zero(0.0)
        assert is_close_zero(1e-15)
        assert not is_close_zero(1.0)
        assert not is_close_zero(float("nan"))

class TestFiniteness:
    def test_finite(self):
        assert is_finite(0.0)
        assert is_finite(1e300)
        assert not is_finite(float("nan"))
        assert not is_finite(float("inf"))
    def test_nan_inf(self):
        assert is_nan(float("nan"))
        assert not is_nan(1.0)
        assert is_inf(float("inf"))
        assert is_inf(float("-inf"))

class TestRequireFinite:
    def test_ok(self):
        assert require_finite(1.0) == 1.0
    def test_raises(self):
        with pytest.raises(ValueError):
            require_finite(float("nan"))
        with pytest.raises(ValueError):
            require_finite(float("inf"), name="x")

class TestSafeDivide:
    def test_normal(self):
        assert safe_divide(6.0, 3.0) == 2.0
    def test_zero_default(self):
        assert safe_divide(1.0, 0.0, default=42.0) == 42.0
    def test_zero_raises(self):
        with pytest.raises(ZeroDivisionError):
            safe_divide(1.0, 0.0)

class TestClamp:
    def test_clamps(self):
        assert clamp(5.0, 0.0, 1.0) == 1.0
        assert clamp(-1.0, 0.0, 1.0) == 0.0
        assert clamp(0.5, 0.0, 1.0) == 0.5
        assert clamp01(2.0) == 1.0
    def test_invalid_range(self):
        with pytest.raises(ValueError):
            clamp(0.5, 1.0, 0.0)

class TestSign:
    def test_sign(self):
        assert sign(3.0) == 1.0
        assert sign(-3.0) == -1.0
        assert sign(0.0) == 0.0
        assert math.isnan(sign(float("nan")))
