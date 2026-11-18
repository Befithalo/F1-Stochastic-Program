# Phase 9: Data and Geometry Readiness

## What was built and why

Phase 9 prepared cutoff-safe inputs for a physics-based pace model. It normalized optional OpenF1 weather, car-data and location channels; pinned and validated the Sakhir track profile; and recorded which pace coefficients can be estimated from race data versus which vehicle properties remain assumptions. Sparse telemetry is reported with an explicit cached-lap fallback. No simulator or strategy consumer was changed.

The evidence screen used 70 complete in-sample races from 2023–2025 and 57,159 clean laps. It estimated an effective lap-number pace slope of -0.0910407 s/lap (SE 0.0256896; 95% interval -0.1413923 to -0.0406891). This is a stability diagnostic, not recovery of physical car parameters. Predictive lap-time sensitivity remains `not_estimable_pre_solver` until the Phase 10 solver exists.

The Milestone 1 baseline remains fixed: podium Brier 0.055456, top-10 Brier 0.144645, finish-interval coverage 82.26% (16,508/20,001), signed stop-timing error +1.174 laps, and team-call agreement 17.22%. PAC-06 remains unmet; this phase did not retune or rescore it.

## How the pieces connect

`RaceSnapshot` is the cutoff-limited input to physics preparation. `PhysicsInput` copies visible optional telemetry and carries versioned geometry and parameter references without retaining a database capability. The public as-of data door reports channel counts and supplies snapshots; the CLI owns source selection and the `AsOfAccessor`. Coverage and parameter reports consume those prepared, cutoff-safe values. The parameter register labels supported effective terms as fitted and hidden physical quantities as assumptions.

## File-by-file tour

- `src/f1si/data/physics_input.py` builds an immutable, cutoff-safe envelope for optional telemetry and records quality/fallback status.
- `src/f1si/data/coverage_audit.py` summarizes optional-channel coverage and the bounded Bahrain probe from injected source rows.
- `src/f1si/geometry/profile.py` loads the pinned Sakhir geometry after checking its manifest digest, units and geometry constraints.
- `src/f1si/parameters/register.py` publishes a versioned register that separates fitted effective pace terms from assumed physical quantities.
- `src/f1si/parameters/sensitivity.py` measures coefficient evidence and leave-one-race-out stability without claiming physical recovery.
- `src/f1si/parameters/report.py` turns supplied race snapshots and coverage evidence into reproducible JSON and a phase closeout report.
- `src/f1si/cli.py` is the boundary that selects OpenF1, opens as-of snapshots, and invokes the Phase 9 report functions.
- `.planning/phases/09-data-and-geometry-readiness/09-PHASE-REPORT.md` records the coverage outcome and fixed M1 baseline.
- `.planning/phases/09-data-and-geometry-readiness/09-VALIDATION.md` records phase verification, including the Ubuntu and Windows CI gate.
- `DECISIONS.md` records the input coverage thresholds, geometry provenance and parameter-classification method.

## Interview questions

### Q1. Does the model recover power, mass or drag from the existing data?

No. Race lap timing supports a small set of effective pace coefficients, but the absolute car parameters are not separately identifiable from the available evidence. The register keeps them as sourced assumptions for later physics work.

### Q2. Can sparse OpenF1 telemetry replace lap timing?

No. Each optional channel carries coverage and timestamp-quality checks. If it misses its threshold, the prepared input records that status and falls back to cached lap timing; it does not interpolate missing telemetry.

### Q3. What does the numeric sensitivity result establish?

It shows how stable the fitted effective coefficient is across the selected races. It does not establish predictive improvement or physical parameter recovery; those need the Phase 10 solver and independent recovery tests.

## Good to know

- The Bahrain probe is bounded to one ten-minute race-clock window and uses the shared cached OpenF1 client.
- The Sakhir raw asset remains local while file-level redistribution terms are unclear.
- Phase 10 must keep the existing `PaceModel` consumer interface and establish parameter recovery on independent synthetic data.
- Keep the M1 baseline values and denominators unchanged in every later phase report.
