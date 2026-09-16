"""Epoch classification tests — parameterized boundaries, not hard-coded."""

from astra.evolution.epoch import EpochBoundaries, EpochClassifier, EvolutionEpoch


def _classifier():
    return EpochClassifier(EpochBoundaries(
        declining_sfr_threshold=0.1,
        degenerate_remnant_fraction=0.5,
        black_hole_dominated_fraction=0.7,
        dark_era_luminous_fraction=0.01,
        model_id="mock",
    ))


def test_stelliferous_when_sfr_high():
    c = _classifier()
    e = c.classify(cosmic_time_gyr=5.0, sfr_density=0.5,
                   remnant_mass_fraction=0.1, bh_mass_fraction=0.001,
                   luminous_mass_fraction=0.1)
    assert e == EvolutionEpoch.STELLIFEROUS


def test_declining_when_sfr_low_but_remnants_low():
    c = _classifier()
    e = c.classify(cosmic_time_gyr=50.0, sfr_density=0.01,
                   remnant_mass_fraction=0.2, bh_mass_fraction=0.01,
                   luminous_mass_fraction=0.05)
    assert e == EvolutionEpoch.DECLINING_STAR_FORMATION


def test_degenerate_when_remnants_dominate():
    c = _classifier()
    e = c.classify(cosmic_time_gyr=1e3, sfr_density=0.0,
                   remnant_mass_fraction=0.7, bh_mass_fraction=0.1,
                   luminous_mass_fraction=0.01)
    assert e == EvolutionEpoch.DEGENERATE


def test_bh_dominated():
    c = _classifier()
    e = c.classify(cosmic_time_gyr=1e6, sfr_density=0.0,
                   remnant_mass_fraction=0.9, bh_mass_fraction=0.8,
                   luminous_mass_fraction=0.001)
    assert e == EvolutionEpoch.BLACK_HOLE_DOMINATED


def test_dark_era_when_luminous_tiny():
    c = _classifier()
    e = c.classify(cosmic_time_gyr=1e12, sfr_density=0.0,
                   remnant_mass_fraction=0.9, bh_mass_fraction=0.1,
                   luminous_mass_fraction=0.005)
    assert e == EvolutionEpoch.DARK_ERA


def test_unknown_when_state_incomplete():
    c = _classifier()
    e = c.classify(cosmic_time_gyr=0.0, sfr_density=None,
                   remnant_mass_fraction=None, bh_mass_fraction=None,
                   luminous_mass_fraction=None)
    assert e == EvolutionEpoch.UNKNOWN


def test_boundaries_are_model_parameterized():
    # Two scenarios with different cosmological parameters yield different boundaries
    b1 = EpochBoundaries(declining_sfr_threshold=0.1,
                         degenerate_remnant_fraction=0.5,
                         black_hole_dominated_fraction=0.7,
                         dark_era_luminous_fraction=0.01,
                         model_id="model-A")
    b2 = EpochBoundaries(declining_sfr_threshold=0.01,
                         degenerate_remnant_fraction=0.8,
                         black_hole_dominated_fraction=0.5,
                         dark_era_luminous_fraction=0.005,
                         model_id="model-B")
    c1 = EpochClassifier(b1)
    c2 = EpochClassifier(b2)
    # Same physical state classifies differently under different boundaries
    state = dict(cosmic_time_gyr=100.0, sfr_density=0.05,
                 remnant_mass_fraction=0.6, bh_mass_fraction=0.6,
                 luminous_mass_fraction=0.006)
    # c1: sfr 0.05 <=0.1 so not stelliferous; remnant 0.6 >=0.5 so not declining;
    #      bh 0.6 <0.7 so not BH; luminous 0.006 <0.01 -> DARK_ERA
    # c2: sfr 0.05 >0.01 -> STELLIFEROUS
    assert c1.classify(**state) == EvolutionEpoch.DARK_ERA
    assert c2.classify(**state) == EvolutionEpoch.STELLIFEROUS
