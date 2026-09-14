import math
import pytest
from astra.core.rng import RNGStream
from astra.mathematics.statistics import (
    uniform, normal, exponential, bernoulli, binomial,
    mean, variance, std, covariance, correlation, percentile,
)

class TestDeterministicSampling:
    def test_uniform_reproducible(self):
        s1 = RNGStream("a", 42); s2 = RNGStream("b", 42)
        v1 = [uniform(s1, 0, 1) for _ in range(10)]
        v2 = [uniform(s2, 0, 1) for _ in range(10)]
        assert v1 == v2
    def test_uniform_range(self):
        s = RNGStream("t", 1)
        for _ in range(100):
            v = uniform(s, 2, 3)
            assert 2.0 <= v < 3.0
    def test_normal_finite(self):
        s = RNGStream("t", 1)
        for _ in range(50):
            assert math.isfinite(normal(s, 0, 1))
    def test_normal_zero_sigma(self):
        s = RNGStream("t", 1)
        assert normal(s, 5.0, 0.0) == 5.0
    def test_exponential(self):
        s = RNGStream("t", 1)
        for _ in range(50):
            assert exponential(s, 1.0) >= 0.0
    def test_exponential_bad_rate(self):
        s = RNGStream("t", 1)
        with pytest.raises(ValueError):
            exponential(s, 0.0)
    def test_bernoulli(self):
        s = RNGStream("t", 1)
        assert bernoulli(s, 0.0) is False
        assert bernoulli(s, 1.0) is True
    def test_binomial(self):
        s = RNGStream("t", 1)
        v = binomial(s, 10, 0.5)
        assert 0 <= v <= 10

class TestStatistics:
    def test_mean(self):
        assert mean([1, 2, 3, 4]) == 2.5
    def test_mean_empty(self):
        with pytest.raises(ValueError):
            mean([])
    def test_variance_population(self):
        assert variance([1, 2, 3, 4], ddof=0) == 1.25
    def test_variance_sample(self):
        assert variance([1, 2, 3, 4], ddof=1) == pytest.approx(5.0 / 3.0)
    def test_std(self):
        assert std([1, 2, 3, 4], ddof=0) == pytest.approx(math.sqrt(1.25))
    def test_covariance(self):
        c = covariance([1, 2, 3], [2, 4, 6])
        assert c > 0
    def test_correlation_perfect(self):
        c = correlation([1, 2, 3], [2, 4, 6])
        assert c == pytest.approx(1.0)
    def test_correlation_zero_std(self):
        with pytest.raises(ValueError):
            correlation([1, 1, 1], [1, 2, 3])
    def test_percentile(self):
        xs = [1, 2, 3, 4, 5]
        assert percentile(xs, 0.0) == 1
        assert percentile(xs, 1.0) == 5
        assert percentile(xs, 0.5) == 3.0
    def test_percentile_empty(self):
        with pytest.raises(ValueError):
            percentile([], 0.5)
