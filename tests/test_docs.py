"""Completeness test for the plain-language explainer and the README (UI-03, D-17)."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPLAINERS = sorted((ROOT / "docs" / "explained").glob("phase-*.md"))
PHASE1 = ROOT / "docs" / "explained" / "phase-01.md"
PHASE2 = ROOT / "docs" / "explained" / "phase-02.md"
PHASE3 = ROOT / "docs" / "explained" / "phase-03.md"
README = ROOT / "README.md"

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
        "hindsight simulation",
        "prior only",
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
