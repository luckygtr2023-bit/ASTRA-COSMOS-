import math
import pytest
from astra.mathematics import Vector3
from astra.physics import (
    Force, ForceApplication, ForceAccumulator, ConstantForce,
    torque_from_force,
    InvalidForceError,
)


class TestForce:
    def test_zero_torque_at_com(self):
        f = Force(Vector3(1.0, 0.0, 0.0))
        assert f.to_torque(Vector3(0, 0, 0)) == Vector3(0, 0, 0)

    def test_off_center_torque(self):
        f = Force(Vector3(1.0, 0.0, 0.0),
                  application_point=Vector3(0.0, 1.0, 0.0))
        # tau = r x F = (0,1,0) x (1,0,0) = (0,0,-1) (right-handed, locked Mathematics convention)
        assert f.to_torque(Vector3(0, 0, 0)) == Vector3(0, 0, -1)

    def test_nan_rejected(self):
        with pytest.raises(InvalidForceError):
            Force(Vector3(float("nan"), 0, 0))


class TestAccumulator:
    def test_add_zero(self):
        acc = ForceAccumulator()
        assert acc.net_force == Vector3(0, 0, 0)
        assert acc.net_torque == Vector3(0, 0, 0)

    def test_net_force(self):
        acc = ForceAccumulator()
        acc.add_raw_force(Vector3(1, 0, 0))
        acc.add_raw_force(Vector3(0, 1, 0))
        assert acc.net_force == Vector3(1, 1, 0)

    def test_add_force_with_offset(self):
        acc = ForceAccumulator()
        f = Force(Vector3(1.0, 0.0, 0.0),
                  application_point=Vector3(0.0, 2.0, 0.0))
        acc.add_force(f, com_world=Vector3(0, 0, 0))
        assert acc.net_force == Vector3(1, 0, 0)
        # tau = r x F = (0,2,0) x (1,0,0) = (0,0,-2) (right-handed)
        assert acc.net_torque == Vector3(0, 0, -2)

    def test_application_point_offset(self):
        acc = ForceAccumulator()
        app = ForceApplication(
            force=Vector3(1.0, 0.0, 0.0),
            application_point_offset=Vector3(0.0, 1.0, 0.0),
        )
        acc.add(app)
        # tau = r x F = (0,1,0) x (1,0,0) = (0,0,-1) (right-handed)
        assert acc.net_torque == Vector3(0, 0, -1)

    def test_pure_torque_added(self):
        acc = ForceAccumulator()
        app = ForceApplication(torque=Vector3(0, 0, 5.0))
        acc.add(app)
        assert acc.net_torque == Vector3(0, 0, 5)

    def test_clear(self):
        acc = ForceAccumulator()
        acc.add_raw_force(Vector3(1, 0, 0))
        acc.clear()
        assert acc.net_force == Vector3(0, 0, 0)


class TestTorque:
    def test_torque_from_force(self):
        tau = torque_from_force(Vector3(0, 1, 0),
                                application_point=Vector3(1, 0, 0),
                                com_world=Vector3(0, 0, 0))
        # tau = r x F = (1,0,0) x (0,1,0) = (0,0,1) (right-handed)
        assert tau == Vector3(0, 0, 1)


class TestConstantForce:
    def test_evaluate(self):
        src = ConstantForce(Vector3(3.0, 0.0, 0.0))
        apps = src.evaluate(1.0, Vector3(0, 0, 0),
                            None, Vector3(0, 0, 0), Vector3(0, 0, 0), 0.01)
        assert len(apps) == 1
        assert apps[0].force == Vector3(3, 0, 0)
