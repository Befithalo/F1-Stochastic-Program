"""The shared clean-lap rule for the stint plot and the tyre-wear fit (PAC-01, D-02, D-22).

A "clean lap" means exactly what the stint plot does not fade: not lap 1, not a pit in-lap, not a
pit out-lap and not run under a safety car, virtual safety car or red flag. Yellow flags (track
status code "2") are NOT faded or dropped; D-22 overrides the word "yellow" in D-02, because a
local yellow rarely changes a whole lap time and dropping them would remove many ordinary laps.

`fade_reason` checks the pit reasons BEFORE the track status, so a stop made under a safety car
is reported as "pit in" or "pit out" and the status is hidden. That order is right for the plot
(one reason per lap) but it cannot tell a green-flag stop from a stop under a safety car. For pit
loss, which must use green-flag stops only, use `slow_status` on the track status directly.

The functions take plain scalars only and import nothing from `f1si.data`.
"""

from typing import Final

FADE_TRACK_CODES: Final = frozenset({"4", "5", "6", "7"})


def slow_status(track_status: object) -> bool:
    """True if the track status string holds a safety car, VSC or red-flag code (4, 5, 6, 7).

    Missing values (None, pandas NA, NaN) and non-strings are False.
    """
    return isinstance(track_status, str) and any(c in FADE_TRACK_CODES for c in track_status)


def fade_reason(lap_number: int, pit_in: bool, pit_out: bool, track_status: object) -> str | None:
    """First matching reason a lap is faded, or None for a clean lap.

    The order is: lap 1, pit in, pit out, safety car/VSC/red.
    """
    if lap_number == 1:
        return "lap 1"
    if pit_in:
        return "pit in"
    if pit_out:
        return "pit out"
    if slow_status(track_status):
        return "safety car/VSC/red"
    return None
