---
schema_version: 1
open_count: 1
waived_count: 0
fixed_count: 2
total_count: 3
last_updated: 2026-11-15T07:14:01.559Z
---

# Broken Windows Ledger

> Cross-phase defect register. With `workflow.windows_enforce` enabled, `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | 06 | deviation | src/f1si/backtest/scoring.py |  | Pre-existing import-ban failures: scoring.py calls numpy.random.default_rng at lines 205, 238, and 319 outside Plan 06-06 scope. | fixed |  | 2026-11-14T10:40:34.229Z | 2026-11-14T10:54:24.251Z |
| 2 | 06 | deviation | tests/backtest/test_metrics.py | 262 | Focused scoring suite has a pre-existing fixture failure: snapshot entries omit driver_number in test_predictions_freeze_before_first_results_open_and_score; unrelated to the RNG factory change. | fixed |  | 2026-11-14T10:54:24.632Z | 2026-11-14T11:06:24.865Z |
| 3 | 06 | unrun-verify | src/f1si/app.py |  | Could not submit default Bahrain 2023 replay because all 70 eligible local races lack scheduled_laps; audited the explicit unavailable-schedule state instead. | open |  | 2026-11-15T07:14:01.559Z |  |

````json
[
  {
    "id": 1,
    "kind": "deviation",
    "phase": "06",
    "file": "src/f1si/backtest/scoring.py",
    "line": null,
    "description": "Pre-existing import-ban failures: scoring.py calls numpy.random.default_rng at lines 205, 238, and 319 outside Plan 06-06 scope.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-11-14T10:40:34.229Z",
    "resolved_at": "2026-11-14T10:54:24.251Z",
    "milestone": "v1.0"
  },
  {
    "id": 2,
    "kind": "deviation",
    "phase": "06",
    "file": "tests/backtest/test_metrics.py",
    "line": 262,
    "description": "Focused scoring suite has a pre-existing fixture failure: snapshot entries omit driver_number in test_predictions_freeze_before_first_results_open_and_score; unrelated to the RNG factory change.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-11-14T10:54:24.632Z",
    "resolved_at": "2026-11-14T11:06:24.865Z",
    "milestone": "v1.0"
  },
  {
    "id": 3,
    "kind": "unrun-verify",
    "phase": "06",
    "file": "src/f1si/app.py",
    "line": null,
    "description": "Could not submit default Bahrain 2023 replay because all 70 eligible local races lack scheduled_laps; audited the explicit unavailable-schedule state instead.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-11-15T07:14:01.559Z",
    "resolved_at": null,
    "milestone": "v1.0"
  }
]
````
