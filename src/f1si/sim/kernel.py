"""Compiled one-lap step of the race simulator (SIM-01 mechanics, SIM-02 speed).

State arrays are lap-major `(n_races, n_cars)` with columns in `RaceState.cars` order: the
car index is the column. Draws are indexed by car, never by position, so a change to one car's
plan cannot move another car's random numbers (common random numbers). `order[r, p]` is the
car at running position `p` (0 = leader); `clock[r, c]` is the cumulative time of car `c` when
it last crossed the line. One call advances every race by one lap.

Lap-time model. The free (clear air) lap time of car `c` on compound `k` with `a` laps already
on the tyres is, with the table entries holding the fitted rate (DEC-077),

    T = mean_tab[c, k, a] + z_off * off_sd[c] + z_wear[k] * wear_sd[k] * (a + 1)
        + eps * sd_tab[c, k, a].

Rules, per race and lap, in this order:

1. Safety-car start. If `sc_left == 0` and `u_sc < sc_rate` then `sc_left = sc_duration`; the
   whole lap runs under the safety car and counts as its first lap. A new safety car starts only
   on a green lap. `sc_fresh` marks a race whose safety car was already active at the cutoff:
   its first simulated lap counts as the start for opportunistic stops (and is cleared).
2. Free times `T` per car.
3. Pit decisions. A planned stop happens when `lap == stop_lap[c, stops_done[c]]`. On a lap an
   SC starts, an `opportunistic` car whose next planned stop lies within
   `[lap, lap + sc_window]`, whose following stop (if any) is at least `min_stint` laps later
   and whose stint being ended has at least `min_stint` laps (`age + 1`), takes that stop now
   (the stop is consumed, the rest of the plan is untouched). The pit
   loss is `pit_loss_sc` on an SC lap, else `pit_loss_green`. The in-lap uses the old tyre; the
   age then resets to 0 and the compound becomes `next_comp[c, k]`; otherwise `age += 1`.
4. Arrival `arr[c] = clock[c] + T_eff + pit_loss`, with `T_eff = sc_slowdown * T[leader]` for
   every car under the safety car (leader = car at position 0 at lap start).
5. Green lap, front to back over positions `p = 1 .. C - 1` with `c = order[p]`, `a` the car
   ahead: if `arr[c] < arr[a] + min_gap_s` then (i) if `a` pitted this lap and `c` did not, `c`
   moves ahead deterministically (no chance, no cost) and the check repeats against the new car
   ahead; otherwise (ii) a pass is attempted with `delta = T[a] - T[c]`, succeeding iff
   `pu[r, c] < pass_probability(delta)`. Success swaps the pair, `arr[c] += pass_cost_s` and
   `arr[a] = max(arr[a], arr[c] + min_gap_s)`; failure holds `c` at `arr[a] + min_gap_s` (dirty
   air). One uniform per car per lap, at most one pass per car per lap. A final sweep over positions
   `p = 1 .. C - 1` then enforces `arr[order[p]] >= arr[order[p - 1]] + min_gap_s` (a car is
   held rather than crossing the line closer than the dirty-air gap behind the car now ahead),
   so after every lap the clocks are strictly increasing along `order` (DEC-086).
6. Safety-car lap: no passing; stable sort of positions by arrival (only pit stops reorder).
   If `sc_left == 1` this is the restart lap: afterwards `arr[order[p]] = arr[order[0]] +
   restart_spacing_s * p`.
7. `clock = arr`; `sc_left` decrements when positive; the lap's SC flag goes to `sc_mask`.

No lapping and no retirements (D-09). All draws are consumed whatever happens. There is no
bounds checking inside the compiled code: the Python caller validates every shape and index
(threat T-03-07). `parallel=True` and `fastmath` are not used, keeping results exact and
identical to the pure-Python twin `lap_step.py_func`.
"""

import math

import numpy as np
from numba import njit
from numpy.typing import NDArray


@njit(cache=True)
def pass_probability(delta: float, threshold_s: float, scale_s: float) -> float:
    """Chance of a pass for a pace gap `delta`: logistic((delta - threshold) / scale)."""
    exponent = (threshold_s - delta) / scale_s
    if exponent > 700.0:  # exp would overflow in the pure-Python twin; the limit is 0
        return 0.0
    return 1.0 / (1.0 + math.exp(exponent))


@njit(cache=True)
def lap_step(
    lap: int,
    mean_tab: NDArray[np.float64],
    sd_tab: NDArray[np.float64],
    u_sc: NDArray[np.float64],
    z_off: NDArray[np.float64],
    z_wear: NDArray[np.float64],
    eps: NDArray[np.float64],
    pu: NDArray[np.float64],
    off_sd: NDArray[np.float64],
    wear_sd: NDArray[np.float64],
    stop_lap: NDArray[np.int64],
    next_comp: NDArray[np.int64],
    opportunistic: NDArray[np.bool_],
    pit_loss_green: float,
    pit_loss_sc: float,
    sc_rate: float,
    sc_duration: int,
    min_gap_s: float,
    threshold_s: float,
    scale_s: float,
    pass_cost_s: float,
    sc_slowdown: float,
    restart_spacing_s: float,
    sc_window: int,
    min_stint: int,
    order: NDArray[np.int64],
    clock: NDArray[np.float64],
    age: NDArray[np.int64],
    comp: NDArray[np.int64],
    stops_done: NDArray[np.int64],
    sc_left: NDArray[np.int64],
    sc_fresh: NDArray[np.bool_],
    pit_paid: NDArray[np.float64],
    stop_taken: NDArray[np.int64],
    sc_mask: NDArray[np.bool_],
) -> None:
    """Advance every race by one lap in place (rules in the module docstring).

    Shapes with `n` races, `C` cars, `K` compounds, `S` stop slots, `A` age rows:
    `mean_tab, sd_tab (C, K, A)`; `u_sc (n,)`; `z_off, eps, pu (n, C)`; `z_wear (n, K)`;
    `off_sd (C,)`; `wear_sd (K,)`; `stop_lap, next_comp (C, S)` (unused stop laps hold a large
    sentinel); `opportunistic (C,)`; mutable `order, clock, age, comp, stops_done (n, C)`,
    `sc_left, sc_fresh (n,)`; outputs `pit_paid (n, C)`, `stop_taken (n, C, S)` (-1 padded),
    `sc_mask (n,)` for this lap.
    """
    n = order.shape[0]
    n_cars = order.shape[1]
    n_stops = stop_lap.shape[1]
    max_age = mean_tab.shape[2] - 1
    free = np.empty(n_cars)
    arr = np.empty(n_cars)
    pitted = np.zeros(n_cars, dtype=np.bool_)
    for r in range(n):
        # 1. safety-car start
        sc_started = False
        if sc_left[r] == 0 and u_sc[r] < sc_rate:
            sc_left[r] = sc_duration
            sc_started = True
        if sc_fresh[r]:
            sc_started = True
            sc_fresh[r] = False
        sc_active = sc_left[r] > 0
        # 2. free times
        for c in range(n_cars):
            k = comp[r, c]
            a_idx = min(age[r, c], max_age)
            free[c] = (
                mean_tab[c, k, a_idx]
                + z_off[r, c] * off_sd[c]
                + z_wear[r, k] * wear_sd[k] * (age[r, c] + 1)
                + eps[r, c] * sd_tab[c, k, a_idx]
            )
        leader_time = free[order[r, 0]]
        pit_loss = pit_loss_sc if sc_active else pit_loss_green
        # 3. pit decisions and 4. arrivals
        for c in range(n_cars):
            pitted[c] = False
            k_stop = stops_done[r, c]
            if k_stop < n_stops:
                nxt = stop_lap[c, k_stop]
                if nxt == lap:
                    pitted[c] = True
                elif sc_started and opportunistic[c] and nxt >= lap and nxt <= lap + sc_window:
                    following_ok = age[r, c] + 1 >= min_stint  # stint being ended is long enough
                    if (
                        following_ok
                        and k_stop + 1 < n_stops
                        and stop_lap[c, k_stop + 1] - lap < min_stint
                    ):
                        following_ok = False
                    if following_ok:
                        pitted[c] = True
            t_eff = sc_slowdown * leader_time if sc_active else free[c]
            arr[c] = clock[r, c] + t_eff
            if pitted[c]:
                arr[c] += pit_loss
                pit_paid[r, c] += pit_loss
                stop_taken[r, c, k_stop] = lap
                comp[r, c] = next_comp[c, k_stop]
                age[r, c] = 0
                stops_done[r, c] = k_stop + 1
            else:
                age[r, c] += 1
        # 5. green lap: front to back, pit reordering, dirty-air hold or pass
        if not sc_active:
            for p in range(1, n_cars):
                c = order[r, p]
                j = p
                while j > 0:
                    a = order[r, j - 1]
                    if arr[c] >= arr[a] + min_gap_s:
                        break
                    if pitted[a] and not pitted[c]:
                        order[r, j - 1] = c
                        order[r, j] = a
                        arr[a] = max(arr[a], arr[c] + min_gap_s)
                        j -= 1
                        continue
                    delta = free[a] - free[c]
                    if pu[r, c] < pass_probability(delta, threshold_s, scale_s):
                        order[r, j - 1] = c
                        order[r, j] = a
                        arr[c] += pass_cost_s
                        arr[a] = max(arr[a], arr[c] + min_gap_s)
                    else:
                        arr[c] = arr[a] + min_gap_s
                    break
            # clock/order invariant (CR-01): a car cannot cross the line closer than the
            # dirty-air gap behind the car now ahead of it; it is held
            for p in range(1, n_cars):
                floor = arr[order[r, p - 1]] + min_gap_s
                if arr[order[r, p]] < floor:
                    arr[order[r, p]] = floor
        else:
            # 6. safety car: stable insertion sort by arrival
            for p in range(1, n_cars):
                c = order[r, p]
                j = p
                while j > 0 and arr[order[r, j - 1]] > arr[c]:
                    order[r, j] = order[r, j - 1]
                    j -= 1
                order[r, j] = c
            if sc_left[r] == 1:
                lead = arr[order[r, 0]]
                for p in range(n_cars):
                    arr[order[r, p]] = lead + restart_spacing_s * p
        # 7. commit
        for c in range(n_cars):
            clock[r, c] = arr[c]
        sc_mask[r] = sc_active
        if sc_left[r] > 0:
            sc_left[r] -= 1
