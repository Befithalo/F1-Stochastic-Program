"""Meaning-bearing colors and contrast helpers for the Streamlit replay."""

from __future__ import annotations

import re

ASPHALT = "#1C1F23"
PITWALL = "#24282D"
RULE = "#3A4047"
CHALK = "#ECEAE4"
FOG = "#9BA1A8"
RECOMMENDATION = "#B69BFF"

TIRE_COLORS = {
    "SOFT": "#FF6B6B",
    "MEDIUM": "#FFD166",
    "HARD": "#ECEAE4",
    "INTERMEDIATE": "#5FD38D",
    "WET": "#65BDFF",
}
TIRE_LETTERS = {
    "SOFT": "S",
    "MEDIUM": "M",
    "HARD": "H",
    "INTERMEDIATE": "I",
    "WET": "W",
}
TIMING_COLORS = {
    "last lap": CHALK,
    "slower": "#FFD166",
    "personal best": "#5FD38D",
    "overall best": FOG,
    "pit lane": "#65BDFF",
}

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def relative_luminance(color: str) -> float:
    """Return WCAG relative luminance for an sRGB hex color."""
    if not _HEX.fullmatch(color):
        raise ValueError(f"Expected a six-digit hex color, got {color!r}")
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
        for value in channels
    ]
    return sum(
        value * weight for value, weight in zip(linear, (0.2126, 0.7152, 0.0722), strict=True)
    )


def contrast_ratio(first: str, second: str) -> float:
    """Return the WCAG contrast ratio between two opaque sRGB hex colors."""
    first_luminance = relative_luminance(first)
    second_luminance = relative_luminance(second)
    lighter, darker = max(first_luminance, second_luminance), min(first_luminance, second_luminance)
    return (lighter + 0.05) / (darker + 0.05)
