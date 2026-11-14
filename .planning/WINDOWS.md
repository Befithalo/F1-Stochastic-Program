---
schema_version: 1
open_count: 1
waived_count: 0
fixed_count: 0
total_count: 1
last_updated: 2026-11-14T10:40:34.229Z
---

# Broken Windows Ledger

> Cross-phase defect register. With `workflow.windows_enforce` enabled, `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | 06 | deviation | src/f1si/backtest/scoring.py |  | Pre-existing import-ban failures: scoring.py calls numpy.random.default_rng at lines 205, 238, and 319 outside Plan 06-06 scope. | open |  | 2026-11-14T10:40:34.229Z |  |

````json
[
  {
    "id": 1,
    "kind": "deviation",
    "phase": "06",
    "file": "src/f1si/backtest/scoring.py",
    "line": null,
    "description": "Pre-existing import-ban failures: scoring.py calls numpy.random.default_rng at lines 205, 238, and 319 outside Plan 06-06 scope.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-11-14T10:40:34.229Z",
    "resolved_at": null,
    "milestone": "v1.0"
  }
]
````
