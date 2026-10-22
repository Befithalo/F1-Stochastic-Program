"""Completeness test for the plain-language explainer and the README (UI-03, D-17)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPLAINER = ROOT / "docs" / "explained" / "phase-01.md"
README = ROOT / "README.md"

HEADINGS = (
    "## What was built and why",
    "## How the pieces connect",
    "## File-by-file tour",
    "## Interview questions",
    "## Good to know",
)


def _text() -> str:
    return EXPLAINER.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    """Text from `heading` to the next second-level heading (or the end)."""
    start = text.index(heading + "\n")
    match = re.search(r"^## ", text[start + len(heading) :], re.MULTILINE)
    end = start + len(heading) + match.start() if match else len(text)
    return text[start:end]


def test_headings_exist_in_order() -> None:
    text = _text()
    positions = [text.index(h + "\n") for h in HEADINGS]
    assert positions == sorted(positions)


def test_interview_questions_have_answers() -> None:
    section = _section(_text(), "## Interview questions")
    parts = re.split(r"^### Q\d+\..*$", section, flags=re.MULTILINE)
    answers = parts[1:]
    assert 3 <= len(answers) <= 5
    for answer in answers:
        assert len(answer.strip()) >= 40


def test_tour_covers_every_module() -> None:
    tour = _section(_text(), "## File-by-file tour")
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
        "docs/explained/phase-01.md",
        "DECISIONS.md",
    ):
        assert needle in readme, needle
