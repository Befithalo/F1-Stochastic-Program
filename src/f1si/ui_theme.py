"""Meaning-bearing colors and contrast helpers for the Streamlit replay."""

from __future__ import annotations

import re

ASPHALT = "#1B1D23"
PITWALL = "#23262E"
RULE = "#30343E"
CHALK = "#F2F2F0"
FOG = "#A9AEB8"
RECOMMENDATION = "#4ADE80"
BETTER = "#4ADE80"
WORSE = "#FF6B6B"
CAUTION = "#F5C518"

TIRE_COLORS = {
    "SOFT": "#E8323C",
    "MEDIUM": "#F5C518",
    "HARD": "#F2F2F0",
    "INTERMEDIATE": "#43B047",
    "WET": "#2F7FD6",
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
    "slower": CAUTION,
    "personal best": BETTER,
    "overall best": "#A78BFA",
    "pit lane": "#2F7FD6",
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
