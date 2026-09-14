"""ASTRA Mathematics layer.

Dependency direction:
    CORE -> MATHEMATICS -> (motion, physics, relativity, ...)

No global randomness. Every stochastic helper takes an explicit
astra.core.rng.RNGStream supplied by the caller.
"""

from astra.mathematics.constants import (
    PI, TAU, HALF_PI, E, SQRT2, SQRT1_2,
    DEFAULT_ATOL, DEFAULT_RTOL, DEFAULT_EPSILON, MACHINE_EPSILON,
)
from astra.mathematics.precision import (
    is_close, is_close_zero, is_finite, is_nan, is_inf,
    require_finite, safe_divide, clamp, clamp01, sign,
)
from astra.mathematics.vectors import Vector2, Vector3, VectorN
from astra.mathematics.matrices import Matrix3, Matrix4
from astra.mathematics.quaternions import Quaternion
from astra.mathematics.geometry import (
    Ray, Plane, Sphere, AABB,
    ray_sphere_intersection, ray_plane_intersection, ray_aabb_intersection,
    point_plane_distance, point_line_distance, segment_segment_distance,
)
from astra.mathematics.transforms import Transform
from astra.mathematics.interpolation import (
    lerp, inverse_lerp, remap, smoothstep, smootherstep,
    bilinear, catmull_rom, hermite,
)
from astra.mathematics.numerical import (
    derivative_central, derivative_forward, derivative_backward,
    trapezoidal, simpson,
    RootResult, bisection, newton_raphson, secant,
)
from astra.mathematics.ode import (
    euler_step, rk4_step, rk45_step, integrate, IntegrationResult,
)
from astra.mathematics.statistics import (
    uniform, normal, exponential, bernoulli, binomial,
    mean, variance, std, covariance, correlation, percentile,
)
from astra.mathematics.validation import (
    require, require_finite, require_positive, require_non_negative,
    require_in_range, require_finite_vector3, require_unit_vector3,
    check_invariant, normalize_preserves_direction,
    quaternion_rotation_preserves_length, matrix_inverse_identity,
)

__all__ = [
    "PI", "TAU", "HALF_PI", "E", "SQRT2", "SQRT1_2",
    "DEFAULT_ATOL", "DEFAULT_RTOL", "DEFAULT_EPSILON", "MACHINE_EPSILON",
    "is_close", "is_close_zero", "is_finite", "is_nan", "is_inf",
    "require_finite", "safe_divide", "clamp", "clamp01", "sign",
    "Vector2", "Vector3", "VectorN",
    "Matrix3", "Matrix4",
    "Quaternion",
    "Ray", "Plane", "Sphere", "AABB",
    "ray_sphere_intersection", "ray_plane_intersection", "ray_aabb_intersection",
    "point_plane_distance", "point_line_distance", "segment_segment_distance",
    "Transform",
    "lerp", "inverse_lerp", "remap", "smoothstep", "smootherstep",
    "bilinear", "catmull_rom", "hermite",
    "derivative_central", "derivative_forward", "derivative_backward",
    "trapezoidal", "simpson",
    "RootResult", "bisection", "newton_raphson", "secant",
    "euler_step", "rk4_step", "rk45_step", "integrate", "IntegrationResult",
    "uniform", "normal", "exponential", "bernoulli", "binomial",
    "mean", "variance", "std", "covariance", "correlation", "percentile",
    "require", "require_finite", "require_positive", "require_non_negative",
    "require_in_range", "require_finite_vector3", "require_unit_vector3",
    "check_invariant", "normalize_preserves_direction",
    "quaternion_rotation_preserves_length", "matrix_inverse_identity",
]
