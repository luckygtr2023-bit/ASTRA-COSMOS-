"""Numerical methods for ASTRA.

- Differentiation: central, forward, backward.
- Integration: trapezoidal, Simpson.
- Root finding: bisection, Newton-Raphson, secant.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Optional
import math


def derivative_central(f, x, h: float = 1e-6) -> float:
    if h <= 0.0:
        raise ValueError("h must be positive")
    return (f(x + h) - f(x - h)) / (2.0 * h)


def derivative_forward(f, x, h: float = 1e-6) -> float:
    if h <= 0.0:
        raise ValueError("h must be positive")
    return (f(x + h) - f(x)) / h


def derivative_backward(f, x, h: float = 1e-6) -> float:
    if h <= 0.0:
        raise ValueError("h must be positive")
    return (f(x) - f(x - h)) / h


def trapezoidal(f, a, b, n: int = 100) -> float:
    if n < 1:
        raise ValueError("n must be >= 1")
    if a == b:
        return 0.0
    h = (b - a) / n
    s = 0.5 * (f(a) + f(b))
    for i in range(1, n):
        s += f(a + i * h)
    return s * h


def simpson(f, a, b, n: int = 100) -> float:
    if n < 2 or n % 2 != 0:
        raise ValueError("n must be even and >= 2")
    if a == b:
        return 0.0
    h = (b - a) / n
    s = f(a) + f(b)
    for i in range(1, n):
        s += (4.0 if i % 2 == 1 else 2.0) * f(a + i * h)
    return s * h / 3.0


@dataclass
class RootResult:
    root: float
    iterations: int
    converged: bool
    residual: float


def bisection(f, a, b, tol: float = 1e-12, max_iter: int = 200) -> RootResult:
    fa = f(a); fb = f(b)
    if fa == 0.0:
        return RootResult(a, 0, True, 0.0)
    if fb == 0.0:
        return RootResult(b, 0, True, 0.0)
    if fa * fb > 0.0:
        raise ValueError("bisection requires f(a) and f(b) of opposite sign")
    lo, hi = a, b
    flo = fa
    for i in range(1, max_iter + 1):
        mid = 0.5 * (lo + hi)
        fm = f(mid)
        if fm == 0.0 or (hi - lo) * 0.5 < tol:
            return RootResult(mid, i, True, fm)
        if flo * fm < 0.0:
            hi = mid
        else:
            lo, flo = mid, fm
    return RootResult(0.5 * (lo + hi), max_iter, False, f(0.5 * (lo + hi)))


def newton_raphson(f, df, x0, tol: float = 1e-12, max_iter: int = 100) -> RootResult:
    x = x0
    for i in range(1, max_iter + 1):
        fx = f(x)
        if abs(fx) < tol:
            return RootResult(x, i, True, fx)
        d = derivative_central(f, x) if df is None else df(x)
        if d == 0.0 or not math.isfinite(d):
            return RootResult(x, i, False, fx)
        x_new = x - fx / d
        if not math.isfinite(x_new):
            return RootResult(x, i, False, fx)
        if abs(x_new - x) < tol:
            return RootResult(x_new, i, True, f(x_new))
        x = x_new
    return RootResult(x, max_iter, False, f(x))


def secant(f, x0, x1, tol: float = 1e-12, max_iter: int = 100) -> RootResult:
    f0 = f(x0); f1 = f(x1)
    for i in range(1, max_iter + 1):
        if abs(f1) < tol:
            return RootResult(x1, i, True, f1)
        if f1 - f0 == 0.0:
            return RootResult(x1, i, False, f1)
        x_new = x1 - f1 * (x1 - x0) / (f1 - f0)
        if not math.isfinite(x_new):
            return RootResult(x1, i, False, f1)
        x0, f0 = x1, f1
        x1, f1 = x_new, f(x_new)
        if abs(x1 - x0) < tol:
            return RootResult(x1, i, True, f1)
    return RootResult(x1, max_iter, False, f1)
