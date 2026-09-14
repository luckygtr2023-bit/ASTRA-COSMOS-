"""Motion integrators.

Each integrator advances a MotionState by dt using the state's own
`acceleration` and `angular_acceleration` as constants over the step
(jerk = 0). Physics may update these fields externally before each step.

Implementations
---------------
- ExplicitEulerIntegrator        : order 1, explicit; position uses old velocity.
- SemiImplicitEulerIntegrator    : order 1, symplectic; position uses new velocity.
- RK4Integrator                  : order 4, classic Runge-Kutta; quaternion
                                   renormalized at the end of each step.

Determinism: no randomness, no wall-clock, no global state.
"""
from __future__ import annotations
from typing import Protocol

from astra.mathematics import Vector3, Quaternion
from astra.motion.state import MotionState, validate_timestep
from astra.motion.kinematics import (
    linear_step_constant_acceleration,
    quaternion_derivative,
    angular_step_constant_omega,
)


class Integrator(Protocol):
    """Protocol for Motion integrators."""
    name: str
    def step(self, state: MotionState, dt: float) -> MotionState: ...


class ExplicitEulerIntegrator:
    name = "explicit_euler"

    def step(self, state: MotionState, dt: float) -> MotionState:
        validate_timestep(dt)
        out = state.copy()
        out.position = out.position + out.velocity * dt
        out.velocity = out.velocity + out.acceleration * dt
        dq = quaternion_derivative(out.orientation, out.angular_velocity)
        out.orientation = (out.orientation + dq * dt).normalized()
        out.angular_velocity = out.angular_velocity + out.angular_acceleration * dt
        out.time = out.time + dt
        return out


class SemiImplicitEulerIntegrator:
    name = "semi_implicit_euler"

    def step(self, state: MotionState, dt: float) -> MotionState:
        validate_timestep(dt)
        out = state.copy()
        out.velocity = out.velocity + out.acceleration * dt
        out.position = out.position + out.velocity * dt
        out.angular_velocity = out.angular_velocity + out.angular_acceleration * dt
        out.orientation = angular_step_constant_omega(
            out.orientation, out.angular_velocity, dt
        )
        out.time = out.time + dt
        return out


class RK4Integrator:
    """Classic RK4 over (position, velocity, orientation, angular_velocity).

    Linear part is exact for constant acceleration (jerk = 0).
    Angular part uses the quaternion derivative; result is renormalized.
    """
    name = "rk4"

    def step(self, state: MotionState, dt: float) -> MotionState:
        validate_timestep(dt)
        out = state.copy()
        p0 = out.position
        v0 = out.velocity
        q0 = out.orientation
        w0 = out.angular_velocity
        a = out.acceleration
        alpha = out.angular_acceleration

        h = dt
        h2 = 0.5 * h

        k1_p, k1_v = v0, a
        k1_q = quaternion_derivative(q0, w0)
        k1_w = alpha

        p1 = p0 + k1_p * h2
        v1 = v0 + k1_v * h2
        q1 = q0 + k1_q * h2
        w1 = w0 + k1_w * h2

        k2_p, k2_v = v1, a
        k2_q = quaternion_derivative(q1, w1)
        k2_w = alpha

        p2 = p0 + k2_p * h2
        v2 = v0 + k2_v * h2
        q2 = q0 + k2_q * h2
        w2 = w0 + k2_w * h2

        k3_p, k3_v = v2, a
        k3_q = quaternion_derivative(q2, w2)
        k3_w = alpha

        p3 = p0 + k3_p * h
        v3 = v0 + k3_v * h
        q3 = q0 + k3_q * h
        w3 = w0 + k3_w * h

        k4_p, k4_v = v3, a
        k4_q = quaternion_derivative(q3, w3)
        k4_w = alpha

        h6 = h / 6.0
        out.position = p0 + (k1_p + k2_p * 2.0 + k3_p * 2.0 + k4_p) * h6
        out.velocity = v0 + (k1_v + k2_v * 2.0 + k3_v * 2.0 + k4_v) * h6
        q_new = q0 + (k1_q + k2_q * 2.0 + k3_q * 2.0 + k4_q) * h6
        out.orientation = q_new.normalized()
        out.angular_velocity = w0 + (k1_w + k2_w * 2.0 + k3_w * 2.0 + k4_w) * h6
        out.time = out.time + dt
        return out
