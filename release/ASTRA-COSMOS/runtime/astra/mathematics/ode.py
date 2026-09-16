"""Ordinary differential equation integrators for ASTRA.

Interface
---------
Derivative: f(t: float, y: tuple[float, ...]) -> tuple[float, ...]
State y is a tuple of floats. No numpy.

Integrators
-----------
- euler_step (order 1)
- rk4_step   (order 4)
- rk45_step  (Dormand-Prince 5(4), embedded error estimate)
- integrate  (fixed or adaptive driver)
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, List, Tuple

State = Tuple[float, ...]
Deriv = Callable[[float, State], State]


def _add(a: State, b: State) -> State:
    return tuple(x + y for x, y in zip(a, b))


def _scale(s: State, k: float) -> State:
    return tuple(x * k for x in s)


def _combine(*terms) -> State:
    if not terms:
        return ()
    n = len(terms[0][1])
    out = [0.0] * n
    for c, st in terms:
        for i in range(n):
            out[i] += c * st[i]
    return tuple(out)


def euler_step(f: Deriv, t: float, y: State, h: float) -> State:
    if h <= 0.0:
        raise ValueError("h must be positive")
    k1 = f(t, y)
    return _add(y, _scale(k1, h))


def rk4_step(f: Deriv, t: float, y: State, h: float) -> State:
    if h <= 0.0:
        raise ValueError("h must be positive")
    k1 = f(t, y)
    k2 = f(t + 0.5*h, _add(y, _scale(k1, 0.5*h)))
    k3 = f(t + 0.5*h, _add(y, _scale(k2, 0.5*h)))
    k4 = f(t + h, _add(y, _scale(k3, h)))
    return _combine((1.0, y), (h/6.0, k1), (h/3.0, k2), (h/3.0, k3), (h/6.0, k4))


_DP_C = (0.0, 1/5, 3/10, 4/5, 8/9, 1.0, 1.0)
_DP_A = (
    (),
    (1/5,),
    (3/40, 9/40),
    (44/45, -56/15, 32/9),
    (19372/6561, -25360/2187, 64448/6561, -212/729),
    (9017/3168, -355/33, 46732/5247, 49/176, -5103/18656),
    (35/384, 0.0, 500/1113, 125/192, -2187/6784, 11/84),
)
_DP_B5 = (35/384, 0.0, 500/1113, 125/192, -2187/6784, 11/84, 0.0)
_DP_B4 = (5179/57600, 0.0, 7571/16695, 393/640,
          -92097/339200, 187/2100, 1/40)


def rk45_step(f: Deriv, t: float, y: State, h: float) -> Tuple[State, State, float]:
    if h <= 0.0:
        raise ValueError("h must be positive")
    k: List[State] = []
    for i in range(7):
        if i == 0:
            yi = y
        else:
            yi = _combine(*[(1.0, y)] + [(h * _DP_A[i][j], k[j]) for j in range(i)])
        k.append(f(t + _DP_C[i] * h, yi))
    y5 = _combine(*[(1.0, y)] + [(h * _DP_B5[j], k[j]) for j in range(7)])
    y4 = _combine(*[(1.0, y)] + [(h * _DP_B4[j], k[j]) for j in range(7)])
    err = max(abs(a - b) for a, b in zip(y5, y4)) if y5 else 0.0
    return y5, y4, err


@dataclass
class IntegrationResult:
    t: float
    y: State
    steps: int
    accepted: int
    rejected: int


def integrate(f: Deriv, t0: float, y0: State, t_end: float, h: float,
              adaptive: bool = False,
              rtol: float = 1e-9, atol: float = 1e-12,
              max_steps: int = 10_000_000) -> IntegrationResult:
    if h <= 0.0:
        raise ValueError("h must be positive")
    if t_end < t0:
        raise ValueError("t_end must be >= t0")
    t = t0
    y = y0
    steps = accepted = rejected = 0
    while t < t_end:
        if steps >= max_steps:
            raise RuntimeError(f"integrate exceeded max_steps={max_steps}")
        remaining = t_end - t
        step = min(h, remaining)
        if not adaptive:
            y = rk4_step(f, t, y, step)
            t += step
            accepted += 1
        else:
            y5, _y4, err = rk45_step(f, t, y, step)
            scale = atol + rtol * max(abs(v) for v in y5) if y5 else atol
            e = err / scale if scale > 0 else 0.0
            if e <= 1.0:
                y = y5
                t += step
                accepted += 1
                if e > 0:
                    h = step * min(5.0, max(0.2, 0.9 * e ** (-0.2)))
            else:
                rejected += 1
                if e > 0:
                    h = step * max(0.1, 0.9 * e ** (-0.25))
                if h < 1e-15 * max(abs(t), 1.0):
                    raise RuntimeError("adaptive step size underflow")
        steps += 1
    return IntegrationResult(t=t, y=y, steps=steps,
                             accepted=accepted, rejected=rejected)
