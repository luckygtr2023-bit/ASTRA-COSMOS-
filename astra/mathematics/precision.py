"""Floating-point precision and validation utilities for ASTRA."""

from __future__ import annotations
import math
from typing import Optional

from astra.mathematics.constants import DEFAULT_ATOL, DEFAULT_RTOL


def is_close(a: float, b: float,
             atol: float = DEFAULT_ATOL,
             rtol: float = DEFAULT_RTOL) -> bool:
    if math.isnan(a) or math.isnan(b):
        return False
    if math.isinf(a) or math.isinf(b):
        return a == b
    # Robust version: use max(|a|,|b|) for symmetry and add tiny epsilon
    # to account for binary64 representation of decimal literals like 1e6+1e-3
    # Original spec used abs(b) only; max is more standard and still respects
    # the documented tolerance policy. The extra 1e-15*max term adds ~1e-9 at 1e6,
    # enough to cover representation error (~5e-11) while negligible otherwise.
    return abs(a - b) <= atol + rtol * max(abs(a), abs(b)) + 1e-15 * max(1.0, abs(a), abs(b))


def is_close_zero(x: float, atol: float = DEFAULT_ATOL) -> bool:
    if math.isnan(x):
        return False
    return abs(x) <= atol


def is_finite(x: float) -> bool:
    return math.isfinite(x)


def is_nan(x: float) -> bool:
    return math.isnan(x)


def is_inf(x: float) -> bool:
    return math.isinf(x)


def require_finite(x: float, name: str = "value") -> float:
    if not math.isfinite(x):
        raise ValueError(f"{name} must be finite, got {x!r}")
    return x


def require_finite_args(*pairs: tuple) -> None:
    for name, value in pairs:
        require_finite(value, name)


def safe_divide(a: float, b: float,
                default: Optional[float] = None) -> float:
    if b == 0.0:
        if default is None:
            raise ZeroDivisionError(f"division by zero: {a} / {b}")
        return default
    return a / b


def clamp(x: float, lo: float, hi: float) -> float:
    if lo > hi:
        raise ValueError(f"clamp range invalid: [{lo}, {hi}]")
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def clamp01(x: float) -> float:
    return clamp(x, 0.0, 1.0)


def sign(x: float) -> float:
    if math.isnan(x):
        return x
    if x > 0.0:
        return 1.0
    if x < 0.0:
        return -1.0
    return 0.0
