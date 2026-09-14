"""Celestial identity tests: determinism, aliases, immutability, persistence."""
import hashlib

import pytest

from astra.celestial import (
    CelestialIdentity,
    DuplicateNodeError,
    create_identity,
    ensure_distinct,
)


class TestDeterministicIdentity:
    def test_same_name_same_id_across_instances(self):
        assert create_identity("Sun").object_id == create_identity("Sun").object_id

    def test_id_matches_documented_derivation(self):
        expected = "ASTRA-" + hashlib.sha256(b"Sun").hexdigest()[:16]
        assert create_identity("Sun").object_id == expected

    def test_different_names_different_ids(self):
        assert create_identity("Sun").object_id != create_identity("Earth").object_id

    def test_no_rng_used(self):
        # Two interpreter runs must agree bit-for-bit (verified via the
        # documented derivation above; this guards against accidental
        # uuid/time-based ids).
        import subprocess
        import sys
        code = "from astra.celestial import create_identity; print(create_identity('Moon').object_id)"
        out1 = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        out2 = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        assert out1.stdout == out2.stdout != ""


class TestAliases:
    def test_alias_round_trip(self):
        ident = create_identity("Sun", (("HIP", "8102"),))
        assert ident.designation_in("HIP") == "8102"
        assert ident.designation_in("TYC") is None  # unknown stays None

    def test_alias_map_is_read_only(self):
        ident = create_identity("Sun", (("HIP", "8102"),))
        with pytest.raises(TypeError):
            ident.alias_map["HIP"] = "9999"

    def test_with_alias_returns_new_identity(self):
        original = create_identity("Sun")
        updated = original.with_alias("HIP", "8102")
        assert updated is not original
        assert original.designation_in("HIP") is None  # original untouched
        assert updated.designation_in("HIP") == "8102"
        assert updated.object_id == original.object_id  # identity stable

    def test_with_alias_replaces_same_catalog(self):
        ident = create_identity("Sun", (("HIP", "1"),)).with_alias("HIP", "8102")
        assert ident.alias_map == {"HIP": "8102"}

    def test_empty_alias_strings_rejected(self):
        with pytest.raises(ValueError):
            create_identity("Sun", (("HIP", ""),))
        with pytest.raises(ValueError):
            create_identity("Sun").with_alias("", "123")

    def test_empty_canonical_name_rejected(self):
        for bad in ("", "   ", None):
            with pytest.raises(ValueError):
                create_identity(bad)


class TestImmutabilityAndPersistence:
    def test_frozen(self):
        ident = create_identity("Sun")
        with pytest.raises(Exception):
            ident.canonical_name = "Sol"

    def test_hashable(self):
        a = create_identity("Sun")
        b = create_identity("Sun")
        assert len({a, b}) == 1

    def test_persistence_round_trip(self):
        ident = create_identity("Sun", (("HIP", "8102"), ("TYC", "1")))
        restored = CelestialIdentity.from_dict(ident.to_dict())
        assert restored == ident
        assert restored.alias_map == ident.alias_map


class TestDistinctness:
    def test_ensure_distinct_passes_unique(self):
        ensure_distinct(create_identity("Sun"), create_identity("Earth"))

    def test_ensure_distinct_rejects_duplicates(self):
        with pytest.raises(DuplicateNodeError):
            ensure_distinct(create_identity("Sun"), create_identity("Sun"))
