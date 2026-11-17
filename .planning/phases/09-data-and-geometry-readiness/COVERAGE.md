# API Coverage — OpenF1

> Full coverage by default. Opt-outs are explicit, reasoned decisions.

| capability | decision | reason |
|---|---|---|
| /car_data | INTEGRATE | Add optional historical car telemetry through the existing rate-limited cache and as-of boundary. |
| /championship_drivers | OPT-OUT | out of this phase's data needs |
| /championship_teams | OPT-OUT | out of this phase's data needs |
| /drivers | INTEGRATE | Reuse the existing normalized driver context used by race loading. |
| /intervals | OPT-OUT | out of this phase's data needs |
| /laps | INTEGRATE | Reuse the existing cached laps as the documented fallback and sensitivity evidence. |
| /location | INTEGRATE | Add optional approximate progress/alignment evidence; never use it as survey-grade geometry. |
| /meetings | OPT-OUT | out of this phase's data needs |
| /overtakes | OPT-OUT | out of this phase's data needs |
| /pit | OPT-OUT | out of this phase's data needs |
| /position | OPT-OUT | out of this phase's data needs |
| /race_control | INTEGRATE | Reuse the existing normalized cutoff-visible race context. |
| /sessions | INTEGRATE | Resolve the Bahrain 2023 Race session identity for the single bounded historical coverage probe. |
| /session_result | OPT-OUT | out of this phase's data needs |
| /starting_grid | OPT-OUT | out of this phase's data needs |
| /stints | INTEGRATE | Reuse the existing normalized stint context and cached-lap fallback. |
| /team_radio | OPT-OUT | out of this phase's data needs |
| /weather | INTEGRATE | Reuse the existing optional weather channel and preserve UTC source time on newly normalized rows. |

Source: [OpenF1 API documentation](https://openf1.org/docs/), endpoint groups inspected 2026-11-17. The eight INTEGRATE rows represent the existing drivers/laps/stints/race-control/weather adapter surface plus new car-data/location coverage and the sessions lookup needed to identify Bahrain 2023. Every other listed endpoint group is OPT-OUT because it is out of this phase's data needs.

## Four-source planning audit

| SOURCE | ID | Feature or requirement | Plan | Status | Notes |
|---|---|---|---|---|---|
| GOAL | SC-1 | Build an auditable cutoff-safe PhysicsInput from cache and optional channels, with coverage and fallback | 09-02 | COVERED | Tasks 09-02-T01 through 09-02-T03; T03 writes the all-catalog and one-race probe artifact |
| GOAL | SC-2 | Select a versioned, unit-checked Bahrain 2023 profile with provenance, quality, rights, and digest | 09-03 | COVERED | Tasks 09-03-T01 and 09-03-T02 |
| GOAL | SC-3 | Publish fitted-effective versus hidden assumptions with evidence, season bounds, uncertainty, and sensitivity | 09-04 | COVERED | Tasks 09-04-T01 through 09-04-T03 |
| REQ | DAT-01 | Provenance-checked cutoff-safe physics input with optional car telemetry, location, weather, explicit coverage | 09-02 | COVERED | Wave 0 contracts 09-01-T01; implementation 09-02-T01 and 09-02-T02; all-catalog audit and one Bahrain probe 09-02-T03 |
| REQ | GEO-01 | Versioned, unit-checked, provenance and rights-reviewed Bahrain 2023 geometry profile | 09-03 | COVERED | Wave 0 contract 09-01-T02; implementation 09-03-T01 and 09-03-T02 |
| REQ | PAR-01 | Inspect effective fitted parameters and hidden assumptions with evidence, bounds, uncertainty, sensitivity | 09-04 | COVERED | Wave 0 contract 09-01-T03; implementation 09-04-T01 through 09-04-T03 |
| RESEARCH | R-01 | Extend existing normalized schemas, rate-limited OpenF1 cache, and AsOfAccessor visibility | 09-02 | COVERED | No model-side HTTP or cache reads; no SQL schema-push tooling |
| RESEARCH | R-02 | Preserve source UTC timestamps, lights-out race-clock mapping, and cutoff visibility | 09-02 | COVERED | Exact-boundary and future-row perturbation tests |
| RESEARCH | R-03 | Keep optional channels optional, report race/channel coverage and quality, and use cached laps when sparse | 09-02 | COVERED | Per-race physics coverage plus every-catalog local row counts and one bounded Bahrain probe; explicit unavailable/sparse status and fallback reason |
| RESEARCH | R-04 | Keep approximate OpenF1 location for progress/alignment and use independent track geometry | 09-02, 09-03 | COVERED | Location is not interpreted as a geometry profile |
| RESEARCH | R-05 | Build immutable prepared values before model construction and preserve PaceModel and all consumers | 09-02 | COVERED | PhysicsInput holds defensive copies and versioned references |
| RESEARCH | R-06 | Pin one Sakhir profile; record source, frame, transform, units, quality, attribution, rights, and SHA-256 | 09-03 | COVERED | Candidate is TUMFTM tracks/Sakhir.csv at a pinned immutable revision |
| RESEARCH | R-07 | Fail closed on missing or invalid geometry; keep asset local/external if redistribution is unclear | 09-03 | COVERED | Raw bytes are not tracked absent file-specific authorization |
| RESEARCH | R-08 | Separate identifiable effective coefficients from hidden quantities and treat regulation values as constraints | 09-04 | COVERED | Existing FitReport terms are labeled observational effective pace coefficients |
| RESEARCH | R-09 | Produce numeric evidence/identifiability sensitivity without implementing the Phase 10 solver | 09-04 | COVERED | Leave-one-race-out stability result; predictive sensitivity marked not_estimable_pre_solver |
| RESEARCH | R-10 | Treat environmental weather as distinct from tire temperature; no direct tire-temperature channel is claimed | 09-02, 09-04 | COVERED | Weather remains an environmental input and tire thermal quantities remain hidden assumptions |
| RESEARCH | R-11 | Use existing dependencies and test conventions; no new FastF1 downloads; require focused tests and phase CI | 09-01 through 09-04 | COVERED | No dependencies added or FastF1 archive requests; pytest/Hypothesis and Ubuntu/Windows CI remain in scope |
| CONTEXT | D-01 | Use only cached rate-limited OpenF1 and as-of-visible telemetry/location/weather; preserve source and race clocks | 09-02 | COVERED | Tasks 09-02-T01 and 09-02-T02 |
| CONTEXT | D-02 | Optional channel coverage/quality, cached-lap fallback, no fabricated data, no cutoff interpolation, no geometry substitution | 09-02 | COVERED | Tasks 09-02-T02 and 09-02-T03 |
| CONTEXT | D-03 | Evaluate versioned Bahrain 2023 profile with source, version, frame, transform, units, checks, attribution, digest | 09-03 | COVERED | Tasks 09-03-T01 and 09-03-T02 |
| CONTEXT | D-04 | Bundle only after file-specific redistribution review; otherwise external/local; fail clearly when unavailable or invalid | 09-03 | COVERED | Task 09-03-T02 records file and source terms and applies the external/local default when unclear |
| CONTEXT | D-05 | Fit only identifiable effective composites and label absolute physical quantities as hidden assumptions | 09-04 | COVERED | Tasks 09-04-T01 and 09-04-T02 |
| CONTEXT | D-06 | Record evidence, season bounds, uncertainty, and sensitivity; regulatory minima remain constraints | 09-04 | COVERED | Tasks 09-04-T01 through 09-04-T03 |
| CONTEXT | D-07 | Promote immutable race-scoped PhysicsInput before hot path; no accessor in model; preserve PaceModel signature and consumers | 09-02 | COVERED | Assumption delta PROMOTE block and Tasks 09-02-T01 and 09-02-T02 |
| CONTEXT | D-08 | Extend existing normalized cache/as-of design; prove cutoffs/source provenance; exclude current results and 2026 holdout | 09-02, 09-04 | COVERED | Tasks 09-02-T01 through 09-02-T03 and 09-04-T02; catalog report contains channel counts only for out-of-sample races |
| CONTEXT | D-09 | Deliver numeric evidence sensitivity now; mark predictive lap-time sensitivity not_estimable_pre_solver and carry to Phase 10 | 09-04 | COVERED | Tasks 09-04-T02 and 09-04-T03 |

No deferred CONTEXT ideas are included in this plan set.
