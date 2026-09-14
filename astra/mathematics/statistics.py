"""Statistics and deterministic random helpers for ASTRA.

All stochastic helpers require an explicit astra.core.rng.RNGStream.
There is no module-level random source.
"""

from __future__ import annotations
from typing import Sequence
import math

from astra.core.rng import RNGStream


def uniform(stream: RNGStream, a: float, b: float) -> float:
    if b < a:
        raise ValueError("uniform: b must be >= a")
    return a + (b - a) * stream.next_float()


def normal(stream: RNGStream, mu: float = 0.0, sigma: float = 1.0) -> float:
    if sigma < 0.0:
        raise ValueError("normal: sigma must be >= 0")
    if sigma == 0.0:
        return mu
    return stream.next_gauss(mu, sigma)


def exponential(stream: RNGStream, rate: float) -> float:
    if rate <= 0.0:
        raise ValueError("exponential: rate must be > 0")
    u = stream.next_float()
    if u == 0.0:
        u = 1e-300
    return -math.log(u) / rate


def bernoulli(stream: RNGStream, p: float) -> bool:
    if not (0.0 <= p <= 1.0):
        raise ValueError("bernoulli: p must be in [0, 1]")
    return stream.next_float() < p


def binomial(stream: RNGStream, n: int, p: float) -> int:
    if n < 0:
        raise ValueError("binomial: n must be >= 0")
    if not (0.0 <= p <= 1.0):
        raise ValueError("binomial: p must be in [0, 1]")
    count = 0
    for _ in range(n):
        if stream.next_float() < p:
            count += 1
    return count


def mean(xs: Sequence[float]) -> float:
    if not xs:
        raise ValueError("mean of empty sequence")
    return sum(xs) / len(xs)


def variance(xs: Sequence[float], ddof: int = 0) -> float:
    n = len(xs)
    if n == 0:
        raise ValueError("variance of empty sequence")
    if n - ddof <= 0:
        raise ValueError("not enough data for the requested ddof")
    m = mean(xs)
    return sum((x - m) ** 2 for x in xs) / (n - ddof)


def std(xs: Sequence[float], ddof: int = 0) -> float:
    return math.sqrt(variance(xs, ddof))


def covariance(xs: Sequence[float], ys: Sequence[float], ddof: int = 0) -> float:
    if len(xs) != len(ys):
        raise ValueError("covariance: sequences must have equal length")
    n = len(xs)
    if n == 0:
        raise ValueError("covariance of empty sequences")
    if n - ddof <= 0:
        raise ValueError("not enough data for the requested ddof")
    mx = mean(xs); my = mean(ys)
    return sum((a - mx) * (b - my) for a, b in zip(xs, ys)) / (n - ddof)


def correlation(xs: Sequence[float], ys: Sequence[float]) -> float:
    sx = std(xs, ddof=1); sy = std(ys, ddof=1)
    if sx == 0.0 or sy == 0.0:
        raise ValueError("correlation undefined when std is zero")
    return covariance(xs, ys, ddof=1) / (sx * sy)


def percentile(sorted_xs: Sequence[float], q: float) -> float:
    if not sorted_xs:
        raise ValueError("percentile of empty sequence")
    if not (0.0 <= q <= 1.0):
        raise ValueError("q must be in [0, 1]")
    n = len(sorted_xs)
    if n == 1:
        return float(sorted_xs[0])
    idx = q * (n - 1)
    lo = int(math.floor(idx)); hi = int(math.ceil(idx))
    if lo == hi:
        return float(sorted_xs[lo])
    frac = idx - lo
    return sorted_xs[lo] * (1 - frac) + sorted_xs[hi] * frac
