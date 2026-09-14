"""Scientific classification tests: epistemic tags cannot be spoofed."""
import pytest

from astra.theoretical import (
    ScientificClassification,
    create_alcubierre_metric,
    create_einstein_rosen_metric,
    create_morris_thorne_metric,
    create_white_hole_metric,
    get_classification_note,
    get_scientific_classification,
)
from astra.spacetime import KerrMetric, MinkowskiMetric, SchwarzschildMetric


def ellipsoid_b(r0):
    return lambda r: r0 * r0 / r  # b'(r0) = -1 < 1 (admissible)


class TestTagsByModel:
    def test_morris_thorne_is_speculative(self):
        mt = create_morris_thorne_metric(10.0, ellipsoid_b(10.0))
        assert get_scientific_classification(mt) is ScientificClassification.SPECULATIVE

    def test_alcubierre_is_speculative(self):
        w = create_alcubierre_metric(2.0, 50.0, 1.0)
        assert get_scientific_classification(w) is ScientificClassification.SPECULATIVE

    def test_einstein_rosen_is_theoretical(self):
        er = create_einstein_rosen_metric(1.989e30)
        assert get_scientific_classification(er) is ScientificClassification.THEORETICAL

    def test_white_hole_is_theoretical(self):
        wh = create_white_hole_metric(1.989e30)
        assert get_scientific_classification(wh) is ScientificClassification.THEORETICAL


class TestEstablishedDefaults:
    def test_spacetime_metrics_are_established(self):
        # Inherited from astra.spacetime: established physics by default.
        for m in (MinkowskiMetric(), SchwarzschildMetric(1.989e30),
                  KerrMetric(1.989e30, 0.3)):
            assert get_scientific_classification(m) is ScientificClassification.ESTABLISHED

    def test_note_text_for_each_level(self):
        mt = create_morris_thorne_metric(10.0, ellipsoid_b(10.0))
        note = get_classification_note(mt)
        assert "speculative" in note.lower()
        er = create_einstein_rosen_metric(1.989e30)
        assert "without observational proof" in get_classification_note(er)


class TestNoSpoofing:
    def test_instance_shadowing_is_ignored(self):
        mt = create_morris_thorne_metric(10.0, ellipsoid_b(10.0))
        try:
            mt.classification = ScientificClassification.ESTABLISHED
        except AttributeError:
            pass  # slots/property protection also acceptable
        # The API reads the CLASS-level tag: spoofing via the instance fails.
        assert get_scientific_classification(mt) is ScientificClassification.SPECULATIVE

    def test_enum_values_fixed(self):
        assert ScientificClassification.ESTABLISHED.value == "ESTABLISHED"
        assert ScientificClassification.THEORETICAL.value == "THEORETICAL"
        assert ScientificClassification.SPECULATIVE.value == "SPECULATIVE"
