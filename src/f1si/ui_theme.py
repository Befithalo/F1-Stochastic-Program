"""Meaning-bearing colors and contrast helpers for the Streamlit replay."""

from __future__ import annotations

import re

ASPHALT = "#1B1D23"
PITWALL = "#23262E"
RULE = "#30343E"
CHALK = "#F2F2F0"
FOG = "#A9AEB8"
RECOMMENDATION = "#4ADE80"
DEFAULT_TEAM_COLOR = "#358C75"
"""FastF1's 2023 Aston Martin color: the page default before a replay picks a team."""
REST_GREY = "#8A8F99"
"""Histogram bars outside the points (P11 and below), lightened to 3:1 on the band."""
GRID_GREY = "#6B7180"
"""Neutral marks: other cars' gap lines, the starting-grid bar, empty dots (3.45:1 on tarmac)."""
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


def mix(color: str, other: str, weight: float) -> str:
    """Return ``weight`` of ``color`` mixed with ``1 - weight`` of ``other`` in sRGB.

    This matches CSS ``color-mix(in srgb, color weight, other)`` for opaque colors.
    """
    if not _HEX.fullmatch(color) or not _HEX.fullmatch(other):
        raise ValueError(f"Expected six-digit hex colors, got {color!r} and {other!r}")
    if not 0.0 <= weight <= 1.0:
        raise ValueError("weight must be between 0 and 1")
    channels = (
        round(int(color[i : i + 2], 16) * weight + int(other[i : i + 2], 16) * (1.0 - weight))
        for i in (1, 3, 5)
    )
    return "#" + "".join(f"{channel:02X}" for channel in channels)


def team_fill(color: str) -> str:
    """The fill behind white text: team color mixed with black (DESIGN_SYSTEM_V2 §3).

    Start at 70% team color and darken in 5% steps until white text reaches 4.5:1, so light
    team colors (Williams ``#64C4FF``) stay readable too.
    """
    for weight in range(70, -5, -5):
        candidate = mix(color.upper(), "#000000", weight / 100)
        if contrast_ratio("#FFFFFF", candidate) >= 4.5:
            return candidate
    return "#000000"


def band_background(color: str) -> str:
    """Decision band surface: team color mixed 22% into tarmac."""
    return mix(color.upper(), ASPHALT, 0.22)


def readable_on(color: str, background: str = ASPHALT, minimum: float = 3.0) -> str:
    """Lighten ``color`` toward chalk in 5% steps until it reaches ``minimum`` contrast.

    Used for team-colored lines and bars, which must keep 3:1 against their surface. A color
    that already passes is returned unchanged (uppercased).
    """
    for step in range(21):
        candidate = mix(CHALK, color.upper(), step / 20)
        if contrast_ratio(candidate, background) >= minimum:
            return candidate
    return CHALK


def _darkest_readable(color: str, minimum: float = 3.0) -> str:
    """Mix ``color`` toward tarmac as far as it can go while keeping ``minimum`` contrast."""
    base = readable_on(color)
    for step in range(8, 21):
        candidate = mix(base, ASPHALT, step / 20)  # step/20 of base, the rest tarmac
        if contrast_ratio(candidate, ASPHALT) >= minimum:
            return candidate
    return base


def fan_band_colors(team_color: str) -> tuple[str, str, str]:
    """Outer (10-90), middle (25-75) and inner (40-60) band colors.

    One team hue at three strengths: the inner band is strongest (lightest on the dark page)
    and the outer band weakest, and every band keeps at least 3:1 against tarmac. The option
    probability strips use the outer and inner colors as their weakest and strongest cells.
    """
    outer = _darkest_readable(team_color)
    base = readable_on(team_color)
    return outer, mix(base, CHALK, 0.85), mix(base, CHALK, 0.62)
