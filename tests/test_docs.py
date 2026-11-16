"""Completeness test for the plain-language explainer and the README (UI-03, D-17)."""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPLAINERS = sorted((ROOT / "docs" / "explained").glob("phase-*.md"))
PHASE1 = ROOT / "docs" / "explained" / "phase-01.md"
PHASE2 = ROOT / "docs" / "explained" / "phase-02.md"
PHASE3 = ROOT / "docs" / "explained" / "phase-03.md"
PHASE4 = ROOT / "docs" / "explained" / "phase-04.md"
PHASE5 = ROOT / "docs" / "explained" / "phase-05.md"
PHASE6 = ROOT / "docs" / "explained" / "phase-06.md"
README = ROOT / "README.md"
PHASE6_REPORT = ROOT / "reports" / "backtest" / "phase-06.json"

HEADINGS = (
    "## What was built and why",
    "## How the pieces connect",
    "## File-by-file tour",
    "## Interview questions",
    "## Good to know",
)


def _text(path: Path = PHASE1) -> str:
    return path.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    """Text from `heading` to the next second-level heading (or the end)."""
    start = text.index(heading + "\n")
    match = re.search(r"^## ", text[start + len(heading) :], re.MULTILINE)
    end = start + len(heading) + match.start() if match else len(text)
    return text[start:end]


@pytest.mark.parametrize("path", EXPLAINERS, ids=lambda p: p.name)
def test_headings_exist_in_order(path: Path) -> None:
    text = _text(path)
    positions = [text.index(h + "\n") for h in HEADINGS]
    assert positions == sorted(positions)


@pytest.mark.parametrize("path", EXPLAINERS, ids=lambda p: p.name)
def test_interview_questions_have_answers(path: Path) -> None:
    section = _section(_text(path), "## Interview questions")
    parts = re.split(r"^### Q\d+\..*$", section, flags=re.MULTILINE)
    answers = parts[1:]
    assert 3 <= len(answers) <= 5
    for answer in answers:
        assert len(answer.strip()) >= 40


def test_tour_covers_every_module() -> None:
    tour = "\n".join(_section(_text(p), "## File-by-file tour") for p in EXPLAINERS)
    modules = sorted(
        p.relative_to(ROOT).as_posix()
        for p in (ROOT / "src" / "f1si").rglob("*.py")
        if p.name != "__init__.py"
    )
    assert modules
    missing = [m for m in modules if m not in tour]
    assert not missing, missing


def test_tour_mentions_guards_and_workflows() -> None:
    tour = _section(_text(), "## File-by-file tour")
    for path in (
        "tests/guards/import_scan.py",
        "tests/guards/scramble.py",
        "tests/fixtures/leaky_consumer.py",
        ".github/workflows/ci.yml",
        ".github/workflows/real-data.yml",
        "DECISIONS.md",
    ):
        assert path in tour, path


def test_readme_commands_and_links() -> None:
    readme = README.read_text(encoding="utf-8")
    for needle in (
        "uv run f1si load",
        "uv run f1si races",
        "uv run f1si plot bahrain-2023",
        "uv run f1si wear bahrain-2023",
        "uv run f1si plan bahrain-2023",
        "docs/explained/phase-01.md",
        "docs/explained/phase-02.md",
        "lower bound",
        "Hindsight plan",
        "compared against",
        "uv run f1si simulate bahrain-2023",
        "docs/explained/phase-03.md",
        "uv run f1si wear-filter bahrain-2023",
        "docs/explained/phase-04.md",
        "hindsight",
        "hindsight simulation",
        "prior only",
        "uv run f1si replay bahrain-2023 --driver ALO",
        "uv run f1si replay bahrain-2023 --driver ALO --lap 20",
        "--risk-aversion",
        "positive simulation count up to 200,000",
        "0 to one less than the race lap count",
        "default 50,000",
        "[0, 1]",
        "default 0.5",
        "docs/explained/phase-05.md",
        "DECISIONS.md",
    ):
        assert needle in readme, needle


def test_phase2_tour_names_new_modules_and_tests() -> None:
    tour = _section(_text(PHASE2), "## File-by-file tour")
    for path in (
        "src/f1si/interfaces.py",
        "src/f1si/state.py",
        "src/f1si/laps.py",
        "src/f1si/pace/linear.py",
        "src/f1si/strategy/free_track.py",
        "src/f1si/plots/wear.py",
        "tests/conformance",
        "tests/guards/consumers.py",
        "tests/test_cli_wear_plan.py",
        "tests/real/test_wear_bahrain.py",
    ):
        assert path in tour, path


def test_phase3_tour_names_new_modules_and_tests() -> None:
    tour = _section(_text(PHASE3), "## File-by-file tour")
    for path in (
        "src/f1si/sim/numpy_backend.py",
        "src/f1si/sim/kernel.py",
        "src/f1si/sim/draws.py",
        "src/f1si/sim/plans.py",
        "src/f1si/sim/borrow.py",
        "src/f1si/sim/constants.py",
        "src/f1si/regime/sc_rate.py",
        "src/f1si/plots/simulate.py",
        "tests/sim",
        "tests/regime",
        "tests/conformance",
        "tests/guards/consumers.py",
        "tests/test_cli_simulate.py",
        "tests/real/test_simulate_bahrain.py",
        "tests/sim/test_benchmark.py",
        "tests/sim/test_variance_reduction.py",
    ):
        assert path in tour, path


def test_phase4_tour_names_new_modules_and_tests() -> None:
    tour = _section(_text(PHASE4), "## File-by-file tour")
    for path in (
        "src/f1si/pace/kalman.py",
        "src/f1si/plots/wear_filter.py",
        "src/f1si/sim/numpy_backend.py",
        "src/f1si/sim/draws.py",
        "src/f1si/state.py",
        "src/f1si/synthetic/generator.py",
        "src/f1si/cli.py",
        "tests/pace/test_kalman_recovery.py",
        "tests/pace/test_kalman_math.py",
        "tests/sim/test_filter_cars.py",
        "tests/sim/test_phase3_reference.py",
        "tests/test_cli_wear_filter.py",
        "tests/plots/test_wear_filter_plot.py",
        "tests/real/test_wear_filter_bahrain.py",
        "tests/guards/consumers.py",
    ):
        assert path in tour, path


def test_phase5_tour_names_strategy_replay_guards_and_docs() -> None:
    tour = _section(_text(PHASE5), "## File-by-file tour")
    for path in (
        "src/f1si/strategy/longstaff.py",
        "src/f1si/sim/numpy_backend.py",
        "src/f1si/cli.py",
        "tests/strategy/test_longstaff.py",
        "tests/test_cli_replay.py",
        "tests/guards/consumers.py",
        "tests/guards/scramble.py",
        "tests/guards/test_future_scramble.py",
        "tests/conformance/registry.py",
        "tests/conformance/test_suites.py",
        "tests/test_docs.py",
        "tests/test_decisions_log.py",
        "DECISIONS.md",
    ):
        assert path in tour, path


def test_phase5_explainer_distinguishes_continuation_from_action_ranking() -> None:
    text = _text(PHASE5)
    for phrase in (
        "conditional-mean continuation",
        "CVaR-aware current-cutoff ranking",
        "does not make this dynamically CVaR-optimal",
        "double-counting",
        "Phase 6",
    ):
        assert phrase in text


def test_phase5_decisions_record_assumptions_and_revisit_path() -> None:
    text = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
    for phrase in (
        "DEC-096",
        "DEC-097",
        "DEC-098",
        "DEC-099",
        "[ASSUMED]",
        "conditional-mean",
        "CVaR10",
        "branch",
        "tie",
        "Phase 6",
        "double-counting",
        "revisit",
    ):
        assert phrase in text


def test_phase6_published_results_match_completed_report_and_disclosures() -> None:
    report = json.loads(PHASE6_REPORT.read_text(encoding="utf-8"))
    readme = README.read_text(encoding="utf-8")
    explainer = _text(PHASE6)
    metrics = report["metrics"]

    for race_id in report["race_ids"]:
        assert race_id in readme

    published_values = (
        report["metadata"]["n_simulations_per_prediction"],
        report["metadata"]["base_seed"],
        report["metadata"]["risk_aversion"],
        metrics["brier_observation_count"],
        metrics["podium_brier"]["model"]["mean"],
        metrics["podium_brier"]["baseline"]["mean"],
        metrics["podium_brier"]["model_minus_baseline_95"]["mean"],
        metrics["podium_brier"]["model_minus_baseline_95"]["low"],
        metrics["podium_brier"]["model_minus_baseline_95"]["high"],
        metrics["top10_brier"]["model"]["mean"],
        metrics["top10_brier"]["baseline"]["mean"],
        metrics["top10_brier"]["model_minus_baseline_95"]["mean"],
        metrics["top10_brier"]["model_minus_baseline_95"]["low"],
        metrics["top10_brier"]["model_minus_baseline_95"]["high"],
        metrics["finish_interval_90"]["covered"],
        metrics["finish_interval_90"]["classified_finishers"],
        metrics["finish_interval_90"]["coverage"]["mean"],
        metrics["finish_interval_90"]["race_cluster_95"]["low"],
        metrics["finish_interval_90"]["race_cluster_95"]["high"],
        metrics["team_strategy_comparison"]["event_count"],
        metrics["team_strategy_comparison"]["top_action_agreement"]["mean"],
        metrics["team_strategy_comparison"]["top_action_agreement"]["race_cluster_95"]["low"],
        metrics["team_strategy_comparison"]["top_action_agreement"]["race_cluster_95"]["high"],
        metrics["team_strategy_comparison"]["stop_timing_error_laps"]["signed"]["mean"],
        metrics["team_strategy_comparison"]["stop_timing_error_laps"]["signed"]["race_cluster_95"][
            "low"
        ],
        metrics["team_strategy_comparison"]["stop_timing_error_laps"]["signed"]["race_cluster_95"][
            "high"
        ],
        metrics["team_strategy_comparison"]["stop_timing_error_laps"]["absolute"]["mean"],
        metrics["team_strategy_comparison"]["stop_timing_error_laps"]["absolute"][
            "race_cluster_95"
        ]["low"],
        metrics["team_strategy_comparison"]["stop_timing_error_laps"]["absolute"][
            "race_cluster_95"
        ]["high"],
        metrics["wear_band_retrospective_proxy"]["coverage"]["covered"],
        metrics["wear_band_retrospective_proxy"]["coverage"]["denominator"],
        metrics["wear_band_retrospective_proxy"]["coverage"]["rate"],
        metrics["wear_band_retrospective_proxy"]["early_fit_bias_s_per_lap"],
        metrics["wear_band_retrospective_proxy"]["own_lap_evidence"]["mean_share"],
        metrics["wear_band_retrospective_proxy"]["own_lap_evidence"]["measurement_count"],
    )
    for value in published_values:
        rendered = {str(value)}
        if isinstance(value, int):
            rendered.add(f"{value:,}")
        assert any(candidate in readme for candidate in rendered), value

    for race_id in metrics["wear_band_retrospective_proxy"]["unavailable_races"]:
        assert race_id in readme

    for text in (readme, explainer):
        for phrase in (
            "fuel load",
            "tire wear",
            "uncalibrated",
            "prior-driven",
            "retrospective proxy",
            "not latent ground truth",
        ):
            assert phrase in text.lower(), phrase

    for phrase in (
        "FastF1",
        "OpenF1",
        "Jolpica",
        "non-commercial",
        "Raw data is never committed or republished",
        "no superiority claim",
        "race-cluster",
        "inclusive empirical inverted-CDF P05/P95",
        "docs/explained/phase-06.md",
    ):
        assert phrase.lower() in readme.lower(), phrase
