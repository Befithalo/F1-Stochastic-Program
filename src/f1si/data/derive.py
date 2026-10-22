"""Source-agnostic derivations the loader runs before a race is written.

Lap cutoffs
-----------
The as-of door answers "what was knowable when the leader finished lap N?". That moment is

    c(0) = 0.0                                   (lights out)
    c(n) = min over cars of lap_end_s of lap n   (the leader's lap-n completion time)

and it is precomputed at load time. Computing `min(lap_end_s)` at query time would read other cars'
lap-n rows, which are in the future of a car that is still on lap n-1; storing the result as a
time-indexed table (visible at `cutoff_s`) keeps every door read a plain `visible_at_s <= cutoff`
filter (DEC-008).

A lap nobody has an end time for is treated as +infinity, then a reverse cumulative minimum

    c(n) = min(c(n), c(n + 1))   for n = max_lap - 1, ..., 0

makes the series non-decreasing. The reverse cumulative minimum only ever moves a cutoff earlier,
which is the safe direction: it can hide a row, never reveal a future one. Trailing laps that stay
+infinity (no car has an end time for them) are dropped.

Clock sanity (WR-03)
--------------------
The reverse cumulative minimum is safe for look-ahead but not for data quality: ONE wrong
`lap_end_s` (a feed glitch of 100 s on lap 10) would pull every earlier cutoff down to it, and
every snapshot from lap 2 to 10 would hide almost all rows. `sanitize_lap_ends` therefore runs
first. A car's lap ends must increase with its lap number and lie in [0, MAX_LAP_END_S]. The
longest strictly increasing run of each car's ends is kept; every other end is set to NA with a
note. An NA end makes the lap visible only at the race end, which is the safe direction. The loader
rejects a race in which more than MAX_BAD_END_FRACTION of the ends had to be dropped.

What remains after that can only come from missing ends: if the raw leader minimum still falls
from lap n to lap n+1, the car that sets the lower value has no lap n end of its own. The reverse
cumulative minimum then repairs the series, and `cutoff_repairs` reports which laps it had to move
so the loader can say so.

Per-lap track status
--------------------
For each lap the status active when the lap started, followed by every status change inside
(lap_start_s, lap_end_s], is joined into one string with consecutive duplicates removed, for
example "1" (green throughout) or "167" (green, then VSC deployed, then VSC ending). Only rows at
or before the lap's end are used, so the value is knowable at the lap's `visible_at_s`.
"""

from __future__ import annotations

from bisect import bisect_left
from typing import Any, Final

import numpy as np
import numpy.typing as npt
import pandas as pd

_GREEN = "1"

# A race lasts at most four hours (red flags included); six hours leaves a wide margin.
MAX_LAP_END_S: Final = 6 * 3600.0
MAX_BAD_END_FRACTION: Final = 0.10
_NOTE_LIMIT: Final = 5


def _float_array(series: pd.Series[Any]) -> npt.NDArray[np.float64]:
    """Convert a numeric series (any nullable dtype) to float64 with NaN for NA."""
    values = (
        pd.to_numeric(series, errors="coerce")
        .astype("Float64")
        .to_numpy(dtype="float64", na_value=np.nan)
    )
    return np.asarray(values, dtype=np.float64)


def _longest_increasing(values: npt.NDArray[np.float64]) -> npt.NDArray[np.bool_]:
    """Mask of one longest strictly increasing subsequence of `values` (patience sorting)."""
    tails: list[float] = []
    tail_index: list[int] = []
    previous = [-1] * len(values)
    for i, value in enumerate(values):
        pos = bisect_left(tails, float(value))
        if pos == len(tails):
            tails.append(float(value))
            tail_index.append(i)
        else:
            tails[pos] = float(value)
            tail_index[pos] = i
        previous[i] = tail_index[pos - 1] if pos > 0 else -1
    keep = np.zeros(len(values), dtype=bool)
    k = tail_index[-1] if tail_index else -1
    while k >= 0:
        keep[k] = True
        k = previous[k]
    return keep


def sanitize_lap_ends(laps: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Set to NA every `lap_end_s` that cannot be right, and say which ones (WR-03).

    Math: an end is dropped if it is not finite or lies outside [0, MAX_LAP_END_S]; then, per
    driver, the ends ordered by lap number must be strictly increasing, so the ends outside one
    longest strictly increasing subsequence are dropped. Dropping only ever makes a lap visible
    later (at the race end), never earlier.

    Args:
        laps: needs `driver_number`, `lap_number`, `lap_end_s`.

    Returns:
        A copy of `laps` with the bad ends set to NA, and notes naming the first five dropped
        ends (driver, lap, value) plus a count of the rest.
    """
    ends = _float_array(laps["lap_end_s"])
    numbers = pd.to_numeric(laps["lap_number"], errors="coerce").to_numpy(dtype="float64")
    drivers = pd.to_numeric(laps["driver_number"], errors="coerce").to_numpy(dtype="float64")
    bad = ~np.isnan(ends) & ~((ends >= 0.0) & (ends <= MAX_LAP_END_S))  # also catches +-inf
    usable = ~np.isnan(ends) & ~bad & ~np.isnan(numbers) & ~np.isnan(drivers)
    for driver in np.unique(drivers[usable]):
        rows = np.flatnonzero(usable & (drivers == driver))
        rows = rows[np.argsort(numbers[rows], kind="stable")]
        bad[rows[~_longest_increasing(ends[rows])]] = True
    out = laps.copy()
    if not bool(bad.any()):
        return out, []
    column = out["lap_end_s"].astype("Float64")
    out["lap_end_s"] = column.mask(pd.Series(bad, index=column.index))
    notes = [
        f"driver {int(drivers[i])} lap {int(numbers[i])} end {ends[i]:.1f} s"
        for i in np.flatnonzero(bad)[:_NOTE_LIMIT]
    ]
    if int(bad.sum()) > _NOTE_LIMIT:
        notes.append(f"and {int(bad.sum()) - _NOTE_LIMIT} more")
    return out, notes


def cutoff_repairs(laps: pd.DataFrame) -> list[int]:
    """Lap numbers whose raw leader minimum was later than the next lap's and had to be lowered.

    Only laps whose own minimum exists are listed. After `sanitize_lap_ends` this can happen only
    when the car that leads lap n+1 has no recorded end for lap n.
    """
    numbers = pd.to_numeric(laps["lap_number"], errors="coerce").to_numpy(dtype="float64")
    ends = _float_array(laps["lap_end_s"])
    valid = ~np.isnan(numbers) & ~np.isnan(ends)
    if not bool(valid.any()):
        return []
    raw = np.full(int(numbers[valid].max()) + 1, np.inf)
    np.minimum.at(raw, numbers[valid].astype(int), ends[valid])
    repaired = np.minimum.accumulate(raw[::-1])[::-1]
    return [int(n) for n in np.flatnonzero(np.isfinite(raw) & (repaired < raw)) if n >= 1]


def derive_lap_cutoffs(race_id: str, laps: pd.DataFrame) -> pd.DataFrame:
    """Return the leader's lap-completion time for laps 0..max lap.

    Math: c(0) = 0; c(n) = min of non-null `lap_end_s` over rows with `lap_number == n`
    (+inf when none); then the reverse cumulative minimum c(n) = min(c(n), c(n + 1)) makes the
    series non-decreasing; trailing +inf rows are dropped.

    Args:
        race_id: written into the `race_id` column.
        laps: a laps frame with at least `lap_number` and `lap_end_s`.

    Returns:
        Columns `race_id`, `lap`, `cutoff_s`, one row per lap from 0 to the last lap that has any
        end time.
    """
    numbers = pd.to_numeric(laps["lap_number"], errors="coerce").to_numpy(dtype="float64")
    ends = _float_array(laps["lap_end_s"])
    valid = ~np.isnan(numbers) & ~np.isnan(ends)
    max_lap = int(np.nanmax(numbers)) if bool((~np.isnan(numbers)).any()) else 0

    cutoff = np.full(max_lap + 1, np.inf)
    cutoff[0] = 0.0
    if bool(valid.any()):
        np.minimum.at(cutoff, numbers[valid].astype(int), ends[valid])
    cutoff = np.minimum.accumulate(cutoff[::-1])[::-1]

    finite = np.isfinite(cutoff)
    n_keep = int(finite.nonzero()[0].max()) + 1  # lap 0 is always finite
    return pd.DataFrame(
        {
            "race_id": race_id,
            "lap": np.arange(n_keep),
            "cutoff_s": cutoff[:n_keep],
        }
    )


def annotate_lap_track_status(laps: pd.DataFrame, track_status: pd.DataFrame) -> pd.Series[Any]:
    """Return, per lap, the track statuses seen from its start to its end as one string.

    Math: let the status rows be sorted by time. The first character is the status of the last
    row with `t_s <= lap_start_s` ("1" if there is none); then the statuses of rows with
    `lap_start_s < t_s <= lap_end_s` follow in time order. Consecutive duplicates collapse. A lap
    with an NA start or end gets NA, because its window is unknown.

    Args:
        laps: needs `lap_start_s` and `lap_end_s`.
        track_status: needs `t_s` and `status` (and `seq` to break time ties, when present).

    Returns:
        An object Series aligned with `laps.index`.
    """
    if len(track_status) == 0:
        times = np.empty(0, dtype="float64")
        codes: list[str] = []
    else:
        ordered = track_status.assign(
            _t=_float_array(track_status["t_s"]),
            _seq=(
                _float_array(track_status["seq"])
                if "seq" in track_status.columns
                else np.arange(len(track_status), dtype="float64")
            ),
        ).sort_values(["_t", "_seq"], kind="stable")
        times = ordered["_t"].to_numpy(dtype="float64")
        codes = [str(v) for v in ordered["status"]]

    starts = _float_array(laps["lap_start_s"])
    ends = _float_array(laps["lap_end_s"])
    out: list[object] = []
    for start, end in zip(starts, ends, strict=True):
        if np.isnan(start) or np.isnan(end):
            out.append(pd.NA)
            continue
        before = int(np.searchsorted(times, start, side="right"))
        upto = int(np.searchsorted(times, end, side="right"))
        sequence = [codes[before - 1] if before > 0 else _GREEN, *codes[before:upto]]
        collapsed = [c for i, c in enumerate(sequence) if i == 0 or c != sequence[i - 1]]
        out.append("".join(collapsed))
    return pd.Series(out, index=laps.index, dtype=object)
