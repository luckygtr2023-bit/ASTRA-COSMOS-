"""Deterministic ADQL generation and the 2,000-ly selection constant."""

import hashlib

import pytest

from astra.ingestion import (
    COLUMN_NAMES,
    DEFAULT_MAX_RUWE,
    DEFAULT_PARALLAX_OVER_ERROR,
    LY_PER_PARSEC,
    MIN_PARALLAX_MAS_2000LY,
    SELECTION_RADIUS_LY,
    SELECTION_RADIUS_PC,
    DERIVED_COLUMNS,
    GaiaQuerySpec,
    build_adql,
    query_hash,
)
from astra.ingestion.exceptions import IngestionContractError


class TestSelectionConstants:
    def test_2000ly_constant_value(self):
        assert MIN_PARALLAX_MAS_2000LY == pytest.approx(1.63078, abs=1e-6)

    def test_radius_in_parsecs(self):
        assert SELECTION_RADIUS_PC == pytest.approx(613.2036, rel=1e-5)

    def test_constant_is_the_inverse_parallax_of_the_radius(self):
        # parallax[mas] = 1000 / d[pc] -- the derivation, not a hand copy.
        assert MIN_PARALLAX_MAS_2000LY == pytest.approx(
            1000.0 / SELECTION_RADIUS_PC, rel=1e-15
        )

    def test_radius_derived_from_ly(self):
        assert SELECTION_RADIUS_PC == pytest.approx(
            SELECTION_RADIUS_LY / LY_PER_PARSEC, rel=1e-15
        )

    def test_documented_approximation_is_approximate(self):
        # 3.26156 is a rounded IAU conversion: the constant must not pretend
        # to more precision than the input carries.
        assert abs(MIN_PARALLAX_MAS_2000LY - 1.63078) < 1e-5


class TestAdqlDeterminism:
    def test_byte_identical_over_500_builds(self):
        spec = GaiaQuerySpec(min_parallax_mas=MIN_PARALLAX_MAS_2000LY)
        first = build_adql(spec)
        for _ in range(500):
            assert build_adql(spec) == first

    def test_hash_stable_and_matches_sha256(self):
        spec = GaiaQuerySpec(min_parallax_mas=MIN_PARALLAX_MAS_2000LY)
        adql = build_adql(spec)
        expected = hashlib.sha256(adql.encode("utf-8")).hexdigest()
        assert query_hash(adql) == expected
        assert query_hash(build_adql(spec)) == expected

    def test_different_spec_different_hash(self):
        a = query_hash(build_adql(GaiaQuerySpec()))
        b = query_hash(build_adql(GaiaQuerySpec(min_parallax_mas=1.0)))
        assert a != b

    def test_column_order_canonicalized(self):
        scrambled = GaiaQuerySpec(columns=tuple(reversed(COLUMN_NAMES)))
        assert scrambled.columns == COLUMN_NAMES
        assert build_adql(scrambled) == build_adql(GaiaQuerySpec())

    def test_spec_is_frozen(self):
        spec = GaiaQuerySpec()
        with pytest.raises(Exception):
            spec.max_ruwe = 2.0  # frozen dataclass (attr immutability)


class TestAdqlContent:
    def test_selects_all_columns_from_dr3(self):
        adql = build_adql(GaiaQuerySpec())
        assert adql.startswith("SELECT " + ", ".join(COLUMN_NAMES))
        assert "FROM gaiadr3.gaia_source" in adql

    def test_default_quality_gates(self):
        adql = build_adql(GaiaQuerySpec())
        assert "parallax IS NOT NULL" in adql
        assert f"parallax_over_error > {repr(DEFAULT_PARALLAX_OVER_ERROR)}" in adql
        assert f"ruwe < {repr(DEFAULT_MAX_RUWE)}" in adql

    def test_2000ly_clause_uses_named_constant(self):
        adql = build_adql(GaiaQuerySpec(min_parallax_mas=MIN_PARALLAX_MAS_2000LY))
        assert f"parallax >= {repr(MIN_PARALLAX_MAS_2000LY)}" in adql
        assert "parallax >= 1.63078" in adql

    def test_no_distance_clause_when_unbounded(self):
        adql = build_adql(GaiaQuerySpec())
        assert "parallax >=" not in adql

    def test_gates_are_configurable(self):
        adql = build_adql(GaiaQuerySpec(parallax_over_error=2.0, max_ruwe=1.2))
        assert "parallax_over_error > 2.0" in adql
        assert "ruwe < 1.2" in adql


class TestSpecValidation:
    @pytest.mark.parametrize("bad", [0.0, -1.0, float("nan"), float("inf"), True, "5"])
    def test_invalid_parallax_over_error(self, bad):
        with pytest.raises(IngestionContractError):
            GaiaQuerySpec(parallax_over_error=bad)

    @pytest.mark.parametrize("bad", [0.0, -0.5, float("nan"), float("-inf"), False])
    def test_invalid_max_ruwe(self, bad):
        with pytest.raises(IngestionContractError):
            GaiaQuerySpec(max_ruwe=bad)

    @pytest.mark.parametrize("bad", [0.0, -2.0, float("nan"), float("inf")])
    def test_invalid_min_parallax(self, bad):
        with pytest.raises(IngestionContractError):
            GaiaQuerySpec(min_parallax_mas=bad)

    def test_none_min_parallax_is_legal(self):
        spec = GaiaQuerySpec()
        assert spec.min_parallax_mas is None

    def test_unknown_column_rejected(self):
        with pytest.raises(IngestionContractError):
            GaiaQuerySpec(columns=("source_id", "not_a_gaia_column"))

    def test_empty_columns_rejected(self):
        with pytest.raises(IngestionContractError):
            GaiaQuerySpec(columns=())

    def test_derived_columns_are_exactly_gspphot(self):
        assert DERIVED_COLUMNS == (
            "teff_gspphot",
            "logg_gspphot",
            "mh_gspphot",
            "distance_gspphot",
            "ag_gspphot",
        )
        real = [c for c in COLUMN_NAMES if c not in DERIVED_COLUMNS]
        assert len(real) + len(DERIVED_COLUMNS) == 26
