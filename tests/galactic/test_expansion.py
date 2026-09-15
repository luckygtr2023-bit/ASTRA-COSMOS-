"""Expansion double-counting tests."""
from astra.galactic.velocity import hubble_flow_velocity, VelocityDecomposition, decompose_velocity
from astra.galactic.types import Vec3
from astra.galactic.errors import GalacticNumericalError
import pytest


def test_hubble_flow_direction():
    v = hubble_flow_velocity(Vec3(1.0, 0.0, 0.0), h0_kms_mpc=70.0)
    assert v.x > 0.0
    assert v.y == 0.0


def test_hubble_flow_scales_linearly():
    v1 = hubble_flow_velocity(Vec3(1.0, 0.0, 0.0), h0_kms_mpc=70.0)
    v2 = hubble_flow_velocity(Vec3(2.0, 0.0, 0.0), h0_kms_mpc=70.0)
    assert v2.x == pytest.approx(2 * v1.x)


def test_velocity_decomposition_sums():
    d = VelocityDecomposition(
        hubble_flow=Vec3(1.0, 0.0, 0.0),
        peculiar_velocity=Vec3(0.0, 2.0, 0.0),
        local_gravity=Vec3(0.0, 0.0, 3.0),
    )
    t = d.total
    assert t.x == 1.0 and t.y == 2.0 and t.z == 3.0


def test_decompose_velocity_uses_hubble():
    pos = Vec3(10.0, 0.0, 0.0)
    pec = Vec3(0.0, 5.0, 0.0)
    grav = Vec3(0.0, 0.0, 1.0)
    d = decompose_velocity(pos, pec, grav, h0_kms_mpc=70.0)
    assert d.hubble_flow.x == pytest.approx(700.0)
    assert d.total.x == pytest.approx(700.0)
    assert d.total.y == 5.0
    assert d.total.z == 1.0


def test_velocity_decomposition_provenance_declared():
    d = VelocityDecomposition(Vec3(), Vec3(), Vec3())
    p = d.provenance()
    assert "hubble_flow" in p and "peculiar_velocity" in p and "local_gravity" in p


def test_hubble_rejects_negative_h0():
    with pytest.raises(GalacticNumericalError):
        hubble_flow_velocity(Vec3(1, 0, 0), h0_kms_mpc=-10)


def test_double_counting_trap():
    """Total must equal sum of components, not 2*Hubble."""
    pos = Vec3(5.0, 0.0, 0.0)
    d = decompose_velocity(pos, Vec3(1, 0, 0), Vec3(2, 0, 0), h0_kms_mpc=70.0)
    # Hubble = 350, peculiar 1, local 2 => total 353
    assert d.total.x == pytest.approx(350.0 + 1.0 + 2.0)
    # Ensure total is not Hubble counted twice (would be 700+...)
    assert d.total.x != pytest.approx(700.0 + 1.0 + 2.0)
