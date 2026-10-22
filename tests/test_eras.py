"""Era mapping (DAT-05)."""

import itertools

import pytest

from f1si.eras import ERAS, GROUND_EFFECT, REG_2026, UnknownEraError, era_for_season


@pytest.mark.parametrize("season", [2023, 2024, 2025])
def test_ground_effect_seasons_are_in_sample(season: int) -> None:
    era = era_for_season(season)
    assert era is GROUND_EFFECT
    assert era.name == "ground_effect_2022_2025"
    assert era.out_of_sample is False


def test_2026_is_out_of_sample() -> None:
    era = era_for_season(2026)
    assert era is REG_2026
    assert era.name == "reg_2026"
    assert era.out_of_sample is True


@pytest.mark.parametrize("season", [2021, 2027])
def test_unknown_season_raises_with_instructions(season: int) -> None:
    with pytest.raises(UnknownEraError) as exc_info:
        era_for_season(season)
    assert "eras.py" in str(exc_info.value)
    assert str(season) in str(exc_info.value)


def test_era_ranges_do_not_overlap() -> None:
    ordered = sorted(ERAS, key=lambda e: e.first_season)
    for earlier, later in itertools.pairwise(ordered):
        assert earlier.last_season < later.first_season
