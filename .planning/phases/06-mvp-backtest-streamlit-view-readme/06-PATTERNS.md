# Phase 6: MVP Backtest, Streamlit View & README - Pattern Map

**Mapped:** 2026-11-13  
**Files analyzed:** 16 planned or implied files  
**Analogs found:** 15 / 16 (role-match or partial; no exact backtest or Streamlit implementation exists)

## Scope and File Classification

The suggested backtest layout in `06-RESEARCH.md` is the working file list. `walk_forward.py`, `scoring.py`, `metrics.py`, and `strategy.py` are research recommendations rather than locked paths. The walk-forward driver must build each prediction from the current cutoff and strictly earlier race history; `scoring.py` alone may open final classifications. The app must reuse that shared construction. The ten calendar-selected races and fixed defaults are specified in `06-CONTEXT.md`; the UI behavior and labels are specified in `06-UI-SPEC.md`.

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/f1si/backtest/__init__.py` | package | transform | No backtest package exists | none |
| `src/f1si/backtest/walk_forward.py` | service / orchestrator | batch, transform | `src/f1si/cli.py::_replay_at_cutoff` | role-match; cutoff construction |
| `src/f1si/backtest/scoring.py` | service | transform, results read | `src/f1si/data/results.py::ResultsAccessor` | partial; data-door contract, no scoring analog |
| `src/f1si/backtest/metrics.py` | utility | transform | `tests/strategy/test_longstaff.py` | partial; deterministic pure-math test style, no evaluation-metrics analog |
| `src/f1si/backtest/strategy.py` | service | event-driven, transform | `src/f1si/cli.py::_actual_strategy` | partial; extracts actual stop events, no recommendation/event matcher |
| `src/f1si/app.py` | component / page | request-response | `src/f1si/plots/simulate.py` | partial; plot data and Figure conventions; no Streamlit app exists |
| `tests/backtest/test_walk_forward.py` | test | batch, transform | `tests/guards/test_future_scramble.py`; `tests/test_cli_replay.py` | role-match; look-ahead and replay fixtures |
| `tests/backtest/test_metrics.py` | test | transform | `tests/strategy/test_longstaff.py` | partial; numeric invariants and seeded samples |
| `tests/backtest/test_strategy.py` | test | event-driven | `tests/test_cli_replay.py` | partial; synthetic replay/refusal test patterns; no event-alignment test exists |
| `tests/app/test_app.py` (inferred under research's `tests/app/`) | test | request-response | `tests/plots/test_simulate_plot.py` | partial; prepared-data, visible labels, and Figure tests |
| `tests/guards/consumers.py` | test guard registry | transform | Existing consumer registry in the same file; `tests/guards/test_future_scramble.py` exercises it | role-match |
| `README.md` | documentation | transform | Existing `README.md`; regression checks in `tests/test_docs.py` | role-match |
| `docs/explained/phase-06.md` | documentation | transform | `docs/explained/phase-05.md`; `tests/test_docs.py` | role-match |
| `tests/test_docs.py` | test | transform | Existing phase-explainer and README assertions in the same file | role-match |
| `pyproject.toml` | config | none | Existing project dependency/config table | role-match |
| `uv.lock` | config / generated lock | none | Existing lockfile; regenerate through `uv` | role-match |

`tests/guards/import_scan.py` is an important existing boundary, but the current policy already allows `f1si.backtest` to hold `AsOfAccessor` and already restricts `f1si.data.results` to `f1si.backtest.scoring`. Confirm those rules still cover the final module layout; avoid broadening the results allowance. The research does not lock a separate report filename. Use the existing `reports/` convention only if the plan needs a generated artifact.

## Pattern Assignments

### `src/f1si/backtest/walk_forward.py` (service, batch/transform)

**Analog:** `src/f1si/cli.py::_replay_at_cutoff` (tracked source; lines 949-1015)

**Imports and data-access pattern** (lines 949-970):

```python
def _replay_at_cutoff(
    accessor: asof.AsOfAccessor,
    race_id: str,
    laps_total: int,
    code: str,
    lap: int,
    n_simulations: int,
    risk: float,
    seed: int,
) -> _ReplayCutoff:
    at = asof.AsOf(race_id, lap)
    snapshot = accessor.snapshot(at)
    history = accessor.history(at)
    fit = fit_linear_pace(snapshot)
    pit = measure_pit_loss(snapshot, fit)
    wear = current_stint_snapshots(filter_stints(snapshot, fit))
    state = build_race_state(
        snapshot, fit, laps_total=laps_total, pit_loss_s=pit.median_s, wear_filter=wear
    )
    estimate = estimate_sc_rate(history)
```

**Core pattern:** Rebuild the fit, wear state, race state, and safety-car estimate for each cutoff from its `snapshot` and earlier-only `history`. Continue with the same seeded `LongstaffSchwartzPolicy` construction at lines 991-999, then return a plain result object. Do not initialize a race-end fit and reuse it for earlier cutoffs. Factor this cutoff construction into a shared service that both the backtest driver and app can call; keep Streamlit out of the model/data assembly.

**Fallback/error pattern** (lines 971-1015):

```python
is_fallback = not fit.is_identified or not fit.fitted_compounds
model: PaceModel = fit
if is_fallback:
    fallback = SparsePaceFallback(snapshot)
    model = fallback
    # Keep all fallback inputs derived from this cutoff's snapshot.
try:
    analysis = policy.analyze(state, driver=code)
except ValueError as err:
    return _ReplayCutoff(lap, None, str(err))
```

The app should preserve unavailable vs fallback states and the `uncalibrated` disclosure from lines 1004-1015. The backtest should persist enough fallback information to report which rows were prior-driven.

### `src/f1si/backtest/scoring.py` (service, transform/results read)

**Analog:** `src/f1si/data/results.py::ResultsAccessor` (tracked source; lines 1-8, 20-26, 30-56)

**Boundary and query pattern** (lines 1-8, 20-26):

```python
"""The results door: final outcomes of finished in-sample races.

Only `f1si.backtest.scoring` may import this module; the import ban enforces it.
The 2026 races stay locked here too.
"""

_RESULTS_SQL = (
    "SELECT r.race_id, r.driver_number, e.driver_code, r.final_position, "
    "r.classified_position, r.status, r.points, r.laps_completed, r.total_time_s "
    "FROM results r JOIN entries e ON e.race_id = r.race_id "
    "AND e.driver_number = r.driver_number "
    "WHERE r.race_id = ? ORDER BY r.final_position NULLS LAST, r.driver_number"
)
```

`ResultsAccessor.final_classification(race_id)` validates that the race is complete and in-sample before returning the final rows (lines 36-56). Keep this import and join in `scoring.py`, after predictions have been frozen. No app, replay-builder, metrics, or strategy-comparison module should import `f1si.data.results`, query DuckDB, or import the 2026 door.

**Import-policy pattern:** `tests/guards/import_scan.py` lines 117-130 explicitly permits `f1si.data.results` only from `f1si.backtest.scoring`; lines 73-75 include `f1si.backtest` in replay-driver modules allowed to hold the as-of accessor. Preserve these narrow rules.

### `src/f1si/backtest/metrics.py` (utility, transform)

**Analog:** `tests/strategy/test_longstaff.py` (tracked source; lines 105-130)

**Pure numeric test pattern** (lines 105-115):

```python
def test_cvar_uses_worst_tail_with_fractional_boundary_mass() -> None:
    assert _cvar10(np.arange(1.0, 11.0)) == pytest.approx(10.0)
    assert _cvar10(np.arange(1.0, 21.0)) == pytest.approx(19.5)

def test_score_blend_endpoints_and_invalid_risk() -> None:
    assert _score_option(np.array([1.0, 2.0, 9.0, 10.0]), 0.0) == pytest.approx(5.5)
    assert _score_option(np.array([1.0, 2.0, 9.0, 10.0]), 1.0) == pytest.approx(10.0)
    for risk in (-0.01, 1.01, math.inf, math.nan):
        with pytest.raises(ValueError, match="risk_aversion"):
            LongstaffSchwartzPolicy(..., risk_aversion=risk)
```

Keep Brier, quantile, per-race aggregation, and bootstrap functions deterministic and test boundaries with small explicit arrays. Inject a NumPy `Generator` for bootstrap resampling, as policy determinism is asserted at lines 118-130. There is no existing evaluation metric or race-cluster bootstrap implementation to copy; decisions D-02 to D-06 and the research-selected scoring semantics are authoritative.

### `src/f1si/backtest/strategy.py` (service, event-driven/transform)

**Analog:** `src/f1si/cli.py::_actual_strategy` (tracked source; lines 472-477)

**Observed-stop extraction pattern:**

```python
def _actual_strategy(snapshot: asof.RaceSnapshot, number: int) -> tuple[list[str], list[int]]:
    """The driver's visible compounds in stint order and the in-laps of visible stops."""
    stints = snapshot.stints[snapshot.stints["driver_number"] == number].sort_values("stint")
    tyres = [str(c).upper() for c in stints["compound"].astype("object")]
    pits = snapshot.pit_events[snapshot.pit_events["driver_number"] == number]
    return tyres, [int(k) for k in pits.sort_values("in_lap")["in_lap"]]
```

This extracts observed pit events but does not implement the Phase 6 comparison. The new comparator should pair each event with the latest recommendation cutoff strictly before it, compare top action and first planned stop against the observed event, then reduce within race. Keep the event linkage explicit so one event is not counted once per preceding lap. Whole-race resampling, paired where applicable, follows D-06; no existing team-call confidence interval is available as an analog.

### `src/f1si/app.py` (component/page, request-response)

**Analog:** No Streamlit app exists in the tracked repository. Use the existing plot data / renderer split in `src/f1si/plots/simulate.py` (tracked source; lines 11-13, 49-127), and the behavior contract in `06-UI-SPEC.md`.

**Plot boundary pattern** (plot module lines 11-13):

```python
The data preparation (`prepare_sim_plot_data`) is a pure function of plain arrays and scalars;
it takes no snapshot. The renderer uses the matplotlib `Figure` API directly and never `pyplot`.
```

Keep UI controls at the page edge and pass validated race/driver/cutoff/risk values to shared cutoff-safe construction. Use the fan-chart helper and `st.pyplot` for the figure. The page must not hold `AsOfAccessor` or read final results. Match UI-SPEC defaults (Bahrain 2023, ALO, middle eligible cutoff, 0.5), one form, loading/error replacement, proxy labeling, fallback `UNCALIBRATED` labels, and the read-only single-page scope. Research recommends caching immutable deterministic outputs by the complete data/model/input key; do not cache open accessors or mutable connections.

**App presentation test pattern:** `tests/plots/test_simulate_plot.py` lines 39-60 checks the pure prepared data and visible chart contract:

```python
def test_prepared_data() -> None:
    data = _data()
    assert len(data.probabilities) == 20
    assert abs(float(data.probabilities.sum()) - 1.0) < 1e-12
    assert "prior only: no earlier races" in data.caption

def test_figure_has_one_bar_per_position() -> None:
    fig = build_sim_figure(_data())
    assert isinstance(fig, Figure)
    assert len(fig.axes[0].patches) == 20
```

There is no Streamlit AppTest or page fixture in the repo; keep page/service tests focused on selector options, defaults, unavailable/fallback labels, and empty/error/loading states without requiring a live browser.

### `tests/backtest/test_walk_forward.py` and `tests/guards/consumers.py` (test/guard, transform)

**Analogs:** `tests/guards/test_future_scramble.py` (tracked; especially consumer tests at lines 157-235) and `tests/test_cli_replay.py` (tracked; selected/full replay equivalence at lines 200-250, invalid-input refusal at lines 252-325).

Register the public as-of-consuming backtest entry point in `tests/guards/consumers.py` so the existing future-scramble grid invokes it. Add tests for fixed calendar IDs, eligible cutoff order, prior-only history, 2026 refusal, and unchanged prediction under future-row scrambling. The consumer guard is the strongest match; there is no walk-forward backtest fixture or test suite yet.

**Replay equivalence pattern** (`tests/test_cli_replay.py`, lines 224-250): the selected-cutoff output is compared directly to the matching block from a full replay. Reuse this shape to ensure single-cutoff app output matches the same cutoff in the walk-forward path.

### `tests/backtest/test_metrics.py` and `tests/backtest/test_strategy.py` (test, transform/event-driven)

**Analog:** `tests/strategy/test_longstaff.py` (tracked; lines 105-165, 187-205) for controlled numeric samples, deterministic action ordering, endpoint and fallback assertions. Use small hand-built rows to prove same-mask Brier comparisons, per-race weighting, inclusive empirical quantiles, no same-event recommendation, event-level counts, and seeded bootstrap reproducibility. There is no existing Brier or race-cluster bootstrap test to copy.

### `tests/app/test_app.py` (test, request-response)

**Analog:** `tests/plots/test_simulate_plot.py` (tracked; lines 39-60, 85-89). Assert prepared outputs, displayed labels, and absence of pyplot; app-specific Streamlit tests have no current analog. Keep visual/chart tests on pure functions and page tests on controls/states.

### `README.md`, `docs/explained/phase-06.md`, and `tests/test_docs.py` (documentation/test, transform)

**Analogs:** `README.md` lines 14-22 and 44-46; `docs/explained/phase-05.md`; `tests/test_docs.py` lines 80-111 and 176-193 (all tracked).

The README already puts runnable commands and the phase method link together, then states data credits and the non-redistribution constraint. Add measured ten-race metrics, strategy-call comparison, uncertainty, hidden tire/fuel assumptions, calibration/fallback limits, and data credits only after the fixed scoring run. Follow the phase explainer's required headings and file-tour conventions; extend `tests/test_docs.py` with assertions for Phase 6 links/modules/results, as earlier phase additions do.

**Documentation regression pattern** (`tests/test_docs.py`, lines 80-111):

```python
def test_readme_commands_and_links() -> None:
    readme = README.read_text(encoding="utf-8")
    for needle in (
        "uv run f1si load",
        "uv run f1si races",
        "docs/explained/phase-01.md",
        "Hindsight plan",
        "DECISIONS.md",
    ):
        assert needle in readme, needle
```

### `pyproject.toml` and `uv.lock` (config)

**Analog:** `pyproject.toml` (tracked; lines 7-18, 21-22, 56-61). Add the roadmap-required Streamlit dependency to `[project].dependencies` alongside runtime libraries; preserve the existing Python 3.12 bounds and project lint/test settings. Regenerate `uv.lock` with `uv` rather than editing package resolution by hand. `06-RESEARCH.md` records `streamlit>=1.67,<2` as the selected range after its package legitimacy review; current installed state does not contain Streamlit.

## Shared Patterns

### Cutoff and outcome doors

**Sources:** `src/f1si/data/asof.py` lines 82-117; `src/f1si/data/results.py` lines 1-8 and 30-56; `tests/guards/import_scan.py` lines 117-140.

```python
snapshot = accessor.snapshot(at)
history = accessor.history(at)  # prior completed races only
# In f1si.backtest.scoring, after prediction is frozen:
results = ResultsAccessor(db_path).final_classification(race_id)
```

Only the replay/backtest driver should own the as-of accessor. Only `f1si.backtest.scoring` may read final classifications. Keep 2026 behind its separate out-of-sample door. UI and policy code receive plain snapshots/state/predictions rather than accessors.

### Determinism and uncertainty

**Sources:** `tests/strategy/test_longstaff.py` lines 118-130; `06-CONTEXT.md` D-02 through D-06.

Use the repo's injected `numpy.random.Generator` convention, keep the race as the aggregation and resampling unit, and preserve paired rows for model-minus-baseline comparisons. Report model and baseline on the same driver/cutoff mask. The selected scoring semantics in `06-RESEARCH.md` define first-race neutral priors, treatment of unclassified starters, and inclusive inverted-CDF 5th/95th percentiles.

### Fallback and unavailable states

**Source:** `src/f1si/cli.py` lines 971-1015 and 1030-1059; `tests/test_cli_replay.py` lines 62-103.

Retain distinct fallback, unavailable, and normal result states. Make fallback basis visible and call prior-driven/sparse-fallback rows `UNCALIBRATED`. Keep the strategy reason attached to its ranked table instead of inferring a reason in the UI.

### Documentation and licensing

**Sources:** `README.md` lines 44-46; `tests/test_docs.py` lines 80-111; `06-CONTEXT.md` D-05/D-08.

The measured output and limitations belong in user-facing docs. Preserve OpenF1/Jolpica credit and the raw-data non-redistribution note; present wear-reference checks as retrospective proxies rather than hidden ground truth.

## No Functional Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `src/f1si/backtest/metrics.py` | utility | transform | No Brier, interval-coverage, race-cluster aggregation, or bootstrap module exists. |
| `src/f1si/backtest/strategy.py` event matcher | service | event-driven | Existing code extracts observed pit laps, but does not align them to prior recommendations or bootstrap agreement/timing metrics. |
| `src/f1si/app.py` Streamlit orchestration | component | request-response | No Streamlit package or app module exists; use UI-SPEC plus existing Figure helpers. |
| `tests/backtest/*` evaluation cases | test | transform/event-driven | No backtest test package exists. Reuse existing pytest conventions, synthetic fixtures, and future-scramble guards. |
| `tests/app/*` page cases | test | request-response | No Streamlit page tests or AppTest fixtures exist. |

## Metadata

**Analog search scope:** `src/f1si/`, `tests/`, `docs/explained/`, `README.md`, project config, and Phase 6 context/research/UI contract/roadmap.  
**Tracked-source gate:** All named code analogs were confirmed with `git ls-files`; no runtime mirrors or ignored install copies are referenced.  
**Files scanned:** 16 planned/implied targets and 14 tracked code/document/config analog sources.  
**Pattern extraction date:** 2026-11-13
