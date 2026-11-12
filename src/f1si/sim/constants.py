"""Named simulator constants (documented engineering defaults, none of them fitted).

Every value below is an assumption (A1, A2) chosen so the simulator behaves sensibly; each is
fitted per circuit only in Phase 6. The reasoning is logged in DEC-078 to DEC-080.

- `MIN_GAP_S`: dirty-air hold. A follower closer than this to the car ahead cannot lap at its own
  pace: the turbulent air costs it grip, so it is held at exactly this gap behind the leader.
- `THRESHOLD_S`, `SCALE_S`: the pass chance is a logistic curve in the pace gap `delta`
  (seconds per lap the follower is faster). It is 0.5 at `delta == THRESHOLD_S` and rises over
  roughly `SCALE_S` seconds (DEC-078).
- `PASS_COST_S`: time the passer loses while making the move.
- `SC_SLOWDOWN`: a safety-car lap takes this multiple of the leader's green lap time. Same value
  as the synthetic generator's factor; the generator is deliberately not imported.
- `RESTART_SPACING_S`: restart bunching. On the last safety-car lap the field is compressed to
  this fixed gap between consecutive cars.
- `SC_STOP_WINDOW_LAPS`: when a safety car starts, a free-strategy car whose next planned stop
  is within this many laps takes it now at the cheap safety-car pit loss.
- `START_SPACING_S`: gap between consecutive cars at a standing start of a synthetic race.
- `MAX_CARS`, `MAX_LAPS`, `MAX_RACES`: input bounds used for validation (denial-of-service guard).
"""

from typing import Final

MIN_GAP_S: Final[float] = 0.5  # DEC-078, assumption A1
THRESHOLD_S: Final[float] = 0.4  # DEC-078, assumption A1
SCALE_S: Final[float] = 0.2  # DEC-078, assumption A1
PASS_COST_S: Final[float] = 0.3  # DEC-078, assumption A1
SC_SLOWDOWN: Final[float] = 1.4  # DEC-079, assumption A2
RESTART_SPACING_S: Final[float] = 1.0  # DEC-079, assumption A2
SC_STOP_WINDOW_LAPS: Final[int] = 5  # DEC-079, assumption A2
START_SPACING_S: Final[float] = 0.8  # DEC-079, assumption A2
MAX_CARS: Final[int] = 30  # DEC-080 input bound
MAX_LAPS: Final[int] = 120  # DEC-080 input bound
MAX_RACES: Final[int] = 1_000_000  # DEC-080 input bound
