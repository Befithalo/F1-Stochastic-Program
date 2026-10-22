"""Track status derived from OpenF1 race-control messages (D-07, D-08).

OpenF1 has no track-status feed like the official timing system's, so this module rebuilds one from
race-control messages. It is lower fidelity: it only knows what race control announced, and it has
to assume when a virtual safety car ends and when the safety car comes in.

Status codes (the closed set of `f1si.data.schema.TRACK_STATUS_CODES`)::

    "1" green    "2" yellow    "4" safety car    "5" red flag
    "6" virtual safety car (VSC) deployed        "7" VSC ending

Mapping (messages are matched case-insensitively with whitespace collapsed)::

    category SafetyCar, message contains
      VIRTUAL SAFETY CAR DEPLOYED -> VSC deployed ("6"); also ends a red flag
      VIRTUAL SAFETY CAR ENDING   -> VSC ending ("7"); reverts to no VSC at the next Track-scope
                                     GREEN/CLEAR flag, or 15 s later, whichever comes first
      SAFETY CAR DEPLOYED         -> safety car ("4"); also ends a red flag and any VSC
      SAFETY CAR IN THIS LAP      -> the safety car ends at the first leader lap end strictly after
                                     this message (`leader_lap_end_s`), unless a Track-scope
                                     GREEN/CLEAR flag comes first
    category Flag
      RED                         -> red flag ("5")
      YELLOW / DOUBLE YELLOW      -> yellow in that sector (scope Sector), or track-wide otherwise
      CLEAR, scope Sector         -> removes the yellow of that sector
      GREEN / CLEAR, scope Track  -> (or no scope) clears all yellows, ends a red flag, ends a
                                     safety car that is "in this lap", ends a VSC that is "ending"
      any Flag message containing PIT EXIT is ignored (pit-lane only)
      CHEQUERED, BLUE, BLACK AND WHITE, driver-scope flags: ignored
    every other category (Drs, CarEvent, Other): ignored

Several things can be true at once; the reported status is the highest priority::

    red "5" > safety car "4" > VSC deployed "6" > VSC ending "7" > any yellow "2" > green "1"

The timeline starts implicitly green, so the first row appears with the first change. A row is
emitted only when the status changes. Timed transitions (VSC ending + 15 s, safety car in at the
leader's lap end) fire before any later message is processed and are flushed at the end of input;
their message is "VSC ending complete (assumed +15 s)" or "Safety car in at leader lap end
(assumed)".
"""

import math
from collections.abc import Mapping, Sequence
from typing import Final

import pandas as pd

VSC_ENDING_DELAY_S: Final = 15.0
OUTPUT_COLUMNS: Final = ("seq", "t_s", "status", "message")
_VSC_ENDED_MESSAGE: Final = "VSC ending complete (assumed +15 s)"
_SC_IN_MESSAGE: Final = "Safety car in at leader lap end (assumed)"


def _clean(value: object) -> str:
    """Upper-case text with collapsed whitespace; empty for missing values."""
    if value is None or (isinstance(value, float) and math.isnan(value)) or value is pd.NA:
        return ""
    return " ".join(str(value).upper().split())


def _clean_message(value: object) -> str:
    """The original message text, empty when missing."""
    if value is None or value is pd.NA or (isinstance(value, float) and math.isnan(value)):
        return ""
    return str(value)


def _sector(value: object) -> int | None:
    if value is None or value is pd.NA:
        return None
    try:
        number = float(str(value))
    except ValueError:
        return None
    return None if math.isnan(number) else int(number)


class _State:
    """Everything that can make the track non-green, plus the pending timed transitions."""

    def __init__(self, leader_lap_end_s: Sequence[float]) -> None:
        self.leader_lap_ends = sorted(float(x) for x in leader_lap_end_s)
        self.red = False
        self.sc: str | None = None  # None, "deployed" or "in"
        self.sc_end_t: float | None = None
        self.vsc: str | None = None  # None, "deployed" or "ending"
        self.vsc_end_t: float | None = None
        self.yellows: set[int] = set()

    def status(self) -> str:
        if self.red:
            return "5"
        if self.sc is not None:
            return "4"
        if self.vsc == "deployed":
            return "6"
        if self.vsc == "ending":
            return "7"
        if self.yellows:
            return "2"
        return "1"

    def next_timed(self) -> tuple[float, str] | None:
        """The earliest pending timed transition as (time, kind), or None."""
        pending: list[tuple[float, str]] = []
        if self.vsc == "ending" and self.vsc_end_t is not None:
            pending.append((self.vsc_end_t, "vsc"))
        if self.sc == "in" and self.sc_end_t is not None:
            pending.append((self.sc_end_t, "sc"))
        return min(pending) if pending else None

    def fire(self, kind: str) -> str:
        if kind == "vsc":
            self.vsc = None
            self.vsc_end_t = None
            return _VSC_ENDED_MESSAGE
        self.sc = None
        self.sc_end_t = None
        return _SC_IN_MESSAGE

    def first_lap_end_after(self, t_s: float) -> float | None:
        return next((x for x in self.leader_lap_ends if x > t_s), None)

    def track_clear(self) -> None:
        """GREEN or CLEAR for the whole track."""
        self.yellows.clear()
        self.red = False
        if self.sc == "in":
            self.sc = None
            self.sc_end_t = None
        if self.vsc == "ending":
            self.vsc = None
            self.vsc_end_t = None

    def apply(self, t_s: float, row: Mapping[str, object]) -> None:
        category = _clean(row.get("category")).replace(" ", "")
        message = _clean(row.get("message"))
        if category == "SAFETYCAR":
            self._safety_car(t_s, message)
        elif category == "FLAG":
            self._flag(row, message)

    def _safety_car(self, t_s: float, message: str) -> None:
        if "VIRTUAL SAFETY CAR DEPLOYED" in message:
            self.red = False
            self.vsc = "deployed"
            self.vsc_end_t = None
        elif "VIRTUAL SAFETY CAR ENDING" in message:
            if self.vsc is not None:
                self.vsc = "ending"
                self.vsc_end_t = t_s + VSC_ENDING_DELAY_S
        elif "SAFETY CAR DEPLOYED" in message:
            self.red = False
            self.vsc = None
            self.vsc_end_t = None
            self.sc = "deployed"
            self.sc_end_t = None
        elif "SAFETY CAR IN THIS LAP" in message and self.sc is not None:
            self.sc = "in"
            self.sc_end_t = self.first_lap_end_after(t_s)

    def _flag(self, row: Mapping[str, object], message: str) -> None:
        if "PIT EXIT" in message:
            return
        flag = _clean(row.get("flag"))
        scope = _clean(row.get("scope"))
        if scope == "DRIVER":
            return
        if flag == "RED":
            self.red = True
        elif flag in ("YELLOW", "DOUBLE YELLOW"):
            sector = _sector(row.get("sector")) if scope == "SECTOR" else None
            self.yellows.add(sector if sector is not None else 0)
        elif flag == "CLEAR" and scope == "SECTOR":
            sector = _sector(row.get("sector"))
            if sector is not None:
                self.yellows.discard(sector)
        elif flag in ("GREEN", "CLEAR") and scope in ("TRACK", ""):
            self.track_clear()


def derive_track_status(
    race_control: pd.DataFrame, *, leader_lap_end_s: Sequence[float]
) -> pd.DataFrame:
    """Track-status timeline (columns seq, t_s, status, message) from race-control messages.

    `race_control` has the normalized columns seq, t_s, category, flag, scope, sector, message
    (extra columns are ignored). `leader_lap_end_s` are the times at which the leader completed
    each lap; they decide when "SAFETY CAR IN THIS LAP" takes effect. The full mapping and its
    limits are in the module docstring.
    """
    state = _State(leader_lap_end_s)
    out: list[dict[str, object]] = []
    current = "1"

    def emit(t_s: float, message: str) -> None:
        nonlocal current
        new = state.status()
        if new != current:
            out.append({"seq": len(out), "t_s": float(t_s), "status": new, "message": message})
            current = new

    if len(race_control):
        ordered = race_control[race_control["t_s"].notna()].sort_values(
            ["t_s", "seq"], kind="stable"
        )
        for record in ordered.to_dict("records"):
            row: dict[str, object] = {str(k): v for k, v in record.items()}
            t_s = float(str(row["t_s"]))
            while (timed := state.next_timed()) is not None and timed[0] <= t_s:
                emit(timed[0], state.fire(timed[1]))
            state.apply(t_s, row)
            emit(t_s, _clean_message(row.get("message")))
    while (timed := state.next_timed()) is not None:
        emit(timed[0], state.fire(timed[1]))

    frame = pd.DataFrame(out, columns=list(OUTPUT_COLUMNS))
    frame["seq"] = frame["seq"].astype("int64")
    frame["t_s"] = frame["t_s"].astype("float64")
    return frame
