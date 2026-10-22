"""Race slugs."""

import pytest

from f1si.data.slugs import event_slug


@pytest.mark.parametrize(
    ("name", "season", "expected"),
    [
        ("Bahrain Grand Prix", 2023, "bahrain-2023"),
        ("São Paulo Grand Prix", 2024, "sao-paulo-2024"),
        ("Mexico City Grand Prix", 2025, "mexico-city-2025"),
        ("Alpha Grand Prix", 2023, "alpha-2023"),
    ],
)
def test_event_slug(name: str, season: int, expected: str) -> None:
    assert event_slug(name, season) == expected


@pytest.mark.parametrize("name", ["", "   ", "Grand Prix"])
def test_empty_name_raises(name: str) -> None:
    with pytest.raises(ValueError, match="slug"):
        event_slug(name, 2023)
