"""Black-hole parameter validation, immutability, and serialization tests."""
import dataclasses
import math

import pytest

from astra.core.exceptions import AstraError
from astra.blackhole import (
    BlackHoleModel,
    BlackHoleState,
    InvalidBlackHoleMassError,
    InvalidSpinParameterError,
    create_black_hole,
)
from astra.blackhole.parameters import validate_mass_kg, validate_spin_param

MASS_SUN = 1.989e30  # kg


class TestCreationAndModels:
    def test_schwarzschild_default(self):
        bh = create_black_hole(MASS_SUN)
        assert bh.model is BlackHoleModel.SCHWARZSCHILD
        assert bh.spin_param == 0.0

    def test_kerr_from_nonzero_spin(self):
        bh = create_black_hole(MASS_SUN, 0.7)
        assert bh.model is BlackHoleModel.KERR

    def test_negative_spin_is_kerr(self):
        bh = create_black_hole(MASS_SUN, -0.3)
        assert bh.model is BlackHoleModel.KERR

    def test_extremal_spin_admitted(self):
        assert create_black_hole(MASS_SUN, 1.0).model is BlackHoleModel.KERR
        assert create_black_hole(MASS_SUN, -1.0).model is BlackHoleModel.KERR


class TestMassValidation:
    @pytest.mark.parametrize("bad", [0.0, -1.0, -1e12, float("nan"), float("inf"), float("-inf")])
    def test_bad_mass_rejected(self, bad):
        with pytest.raises(InvalidBlackHoleMassError):
            create_black_hole(bad)

    def test_bad_mass_is_valueerror_and_astraerror(self):
        assert issubclass(InvalidBlackHoleMassError, ValueError)
        assert issubclass(InvalidBlackHoleMassError, AstraError)

    def test_non_numeric_mass_rejected(self):
        with pytest.raises(InvalidBlackHoleMassError):
            validate_mass_kg("1000.0")

    def test_bool_rejected(self):
        # bool is an int subclass; ASTRA treats it as a type error, not mass 1.
        with pytest.raises(InvalidBlackHoleMassError):
            validate_mass_kg(True)


class TestSpinValidation:
    @pytest.mark.parametrize("bad", [1.000000000001, -1.000000000001, 1.1, float("nan"), float("inf")])
    def test_naked_singularity_and_non_finite_rejected(self, bad):
        with pytest.raises(InvalidSpinParameterError):
            create_black_hole(MASS_SUN, bad)

    def test_error_family(self):
        assert issubclass(InvalidSpinParameterError, ValueError)
        assert issubclass(InvalidSpinParameterError, AstraError)

    def test_boundary_exactly_one_admitted(self):
        validate_spin_param(1.0)
        validate_spin_param(-1.0)

    def test_non_numeric_spin_rejected(self):
        with pytest.raises(InvalidSpinParameterError):
            validate_spin_param("fast")


class TestImmutability:
    def test_frozen_dataclass(self):
        bh = create_black_hole(MASS_SUN, 0.5)
        with pytest.raises(dataclasses.FrozenInstanceError):
            bh.mass_kg = 2.0 * MASS_SUN

    def test_frozen_spin(self):
        bh = create_black_hole(MASS_SUN, 0.5)
        with pytest.raises(dataclasses.FrozenInstanceError):
            bh.spin_param = 0.9


class TestSerialization:
    def test_to_dict_canonical_only(self):
        # Contract: ONLY canonical parameters serialize; no derived fields.
        d = create_black_hole(MASS_SUN, 0.5).to_dict()
        assert d == {"mass_kg": MASS_SUN, "spin_param": 0.5}

    def test_round_trip(self):
        bh = create_black_hole(MASS_SUN, -0.75)
        restored = BlackHoleState.from_dict(bh.to_dict())
        assert restored == bh
        assert restored.gravitational_radius == bh.gravitational_radius

    def test_from_dict_defaults_to_schwarzschild(self):
        bh = BlackHoleState.from_dict({"mass_kg": MASS_SUN})
        assert bh.model is BlackHoleModel.SCHWARZSCHILD

    def test_from_dict_revalidates(self):
        with pytest.raises(InvalidSpinParameterError):
            BlackHoleState.from_dict({"mass_kg": MASS_SUN, "spin_param": 2.0})

    def test_geometric_length_properties(self):
        bh = create_black_hole(MASS_SUN, 0.5)
        assert bh.spin_length == pytest.approx(0.5 * bh.gravitational_radius)
