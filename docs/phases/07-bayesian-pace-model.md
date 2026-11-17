# Phase 7: Bayesian Pace Model

Phase 7 added a hierarchical Bayesian lap-time model with car/team, driver, compound, tyre-wear, fuel, event and regulation-era effects. Synthetic recovery tests and an independent NUTS reference checked the model implementation, and replay/backtest can select it explicitly while retaining linear pace as the default.

## Real-data result

The one-shot evaluation used the race group and scoring method committed before scores were read: 2025-01, 2025-02 and 2025-03, with paired clean next-lap targets. It produced 1,348 paired predictions and 1,344 unique driver-target laps.

| Race | Paired predictions | Unique driver-target laps | Linear MAE (s) | Bayesian MAE (s) |
|---|---:|---:|---:|---:|
| 2025-01 | 0 | 0 | — | — |
| 2025-02 | 776 | 773 | 0.4160 | 0.5607 |
| 2025-03 | 572 | 571 | 0.2936 | 0.5090 |
| **Combined** | **1,348** | **1,344** | **0.3640** | **0.5387** |

Bayesian MAE was 48.0% higher than the linear baseline. The 15% improvement requirement PAC-06 is therefore **not met**. The score was not tuned or rerun after this result. The 2025-01 race remains in the locked group and contributes no paired targets.

All real training and target rows come from the 2022–2025 ground-effect era. This evaluation cannot measure a real between-era effect; synthetic recovery of an era term does not replace missing real-era evidence.

The complete measurements and diagnostics are in [reports/pace/phase-07.json](../../reports/pace/phase-07.json). The model and evaluation method are explained in [docs/explained/phase-07.md](../explained/phase-07.md), and decisions are recorded in [DECISIONS.md](../../DECISIONS.md).
