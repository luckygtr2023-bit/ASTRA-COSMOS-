import math
import pytest
from astra.mathematics.interpolation import (
    lerp, inverse_lerp, remap, smoothstep, smootherstep,
    bilinear, catmull_rom, hermite,
)
from astra.mathematics.vectors import Vector3

class TestScalarInterp:
    def test_lerp(self):
        assert lerp(0, 10, 0.5) == 5.0
        assert lerp(0, 10, 0.0) == 0.0
        assert lerp(0, 10, 1.0) == 10.0
        assert lerp(0, 10, 2.0) == 20.0
    def test_inverse_lerp(self):
        assert inverse_lerp(0, 10, 5) == 0.5
        with pytest.raises(ValueError):
            inverse_lerp(1, 1, 0)
    def test_remap(self):
        assert remap(5, 0, 10, 0, 100) == 50.0

class TestSmoothstep:
    def test_endpoints(self):
        assert smoothstep(0, 1, -1) == 0.0
        assert smoothstep(0, 1, 2) == 1.0
        assert smoothstep(0, 1, 0) == 0.0
        assert smoothstep(0, 1, 1) == 1.0
    def test_midpoint(self):
        assert smoothstep(0, 1, 0.5) == 0.5
    def test_invalid(self):
        with pytest.raises(ValueError):
            smoothstep(1, 1, 0.5)
    def test_smootherstep(self):
        assert smootherstep(0, 1, 0.5) == 0.5
        assert smootherstep(0, 1, -1) == 0.0
        assert smootherstep(0, 1, 2) == 1.0

class TestBilinear:
    def test_corners(self):
        assert bilinear(0, 1, 2, 3, 0, 0) == 0
        assert bilinear(0, 1, 2, 3, 1, 0) == 1
        assert bilinear(0, 1, 2, 3, 0, 1) == 2
        assert bilinear(0, 1, 2, 3, 1, 1) == 3
    def test_center(self):
        assert bilinear(0, 1, 2, 3, 0.5, 0.5) == 1.5

class TestCatmullRom:
    def test_endpoints(self):
        p0 = Vector3(0, 0, 0); p1 = Vector3(1, 0, 0)
        p2 = Vector3(2, 0, 0); p3 = Vector3(3, 0, 0)
        assert catmull_rom(p0, p1, p2, p3, 0.0) == p1
        assert catmull_rom(p0, p1, p2, p3, 1.0) == p2

class TestHermite:
    def test_endpoints(self):
        p0 = Vector3(0, 0, 0); p1 = Vector3(1, 0, 0)
        m0 = Vector3(0, 0, 0); m1 = Vector3(0, 0, 0)
        assert hermite(p0, m0, p1, m1, 0.0) == p0
        assert hermite(p0, m0, p1, m1, 1.0) == p1
