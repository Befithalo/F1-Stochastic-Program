"""Structure and coverage test for DECISIONS.md (FND-04).

Later plans append entries with the next free DEC number, so entries are asserted by title or
keyword, never by a number above DEC-014. Extend `REQUIRED_REFS` and `MIN_ENTRIES` when a plan
adds entries.
"""

import re
from pathlib import Path

import pytest

DECISIONS = Path(__file__).resolve().parents[1] / "DECISIONS.md"

# Em dash written as an escape so ruff's ambiguous-unicode rules stay quiet.
HEADING = re.compile("^## (DEC-\\d{3}) — (.+)$", re.MULTILINE)
LABELS = (
    "**Date:**",
    "**Status:**",
    "**Context:**",
    "**Decision:**",
    "**Why:**",
    "**Alternatives rejected:**",
    "**Consequences:**",
    "**Refs:**",
)
REQUIRED_REFS = frozenset(
    {
        "D-01",
        "D-02",
        "D-03",
        "D-04",
        "D-05",
        "D-06",
        "D-07",
        "D-08",
        "D-09",
        "D-10",
        "D-13",
        "D-15",
        "D-16",
    }
)
MIN_ENTRIES = 54


def _entries() -> list[tuple[str, str, str]]:
    """(id, title, body) for each entry, in file order."""
    text = DECISIONS.read_text(encoding="utf-8")
    matches = list(HEADING.finditer(text))
    entries: list[tuple[str, str, str]] = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        entries.append((match.group(1), match.group(2), text[match.end() : end]))
    return entries


def test_ids_are_consecutive_and_enough() -> None:
    ids = [entry_id for entry_id, _, _ in _entries()]
    assert len(ids) >= MIN_ENTRIES
    assert ids == [f"DEC-{n:03d}" for n in range(1, len(ids) + 1)]


def test_every_entry_has_all_labels() -> None:
    for entry_id, _, body in _entries():
        missing = [label for label in LABELS if label not in body]
        assert not missing, f"{entry_id} lacks {missing}"


def test_refs_cover_required_decisions() -> None:
    refs: set[str] = set()
    for _, _, body in _entries():
        for line in body.splitlines():
            if line.startswith("**Refs:**"):
                refs.update(re.findall(r"[A-Z]{1,3}-\d{2,3}", line))
    assert refs >= REQUIRED_REFS, sorted(REQUIRED_REFS - refs)


@pytest.mark.parametrize(
    "keywords",
    [
        ("ground_effect_2022_2025", "reg_2026"),
        ("OpenF1", "Jolpica", "401"),
        ("reverse cumulative minimum",),
        ("RACE_END",),
        ("LapOutOfRangeError",),
        ("responsibility map", "f1si.cli"),
        ("VIRTUAL SAFETY CAR DEPLOYED", "SAFETY CAR IN THIS LAP", "PIT EXIT"),
        ("2.1 s", "450"),
        ("lights out",),
        ("pit_lane_start", "Did not start"),
    ],
)
def test_some_entry_contains_keywords(keywords: tuple[str, ...]) -> None:
    assert any(all(k in body for k in keywords) for _, _, body in _entries()), keywords


def test_cli_source_choice_entry_exists_by_title() -> None:
    assert any(title == "The CLI chooses the data source" for _, title, _ in _entries())


@pytest.mark.parametrize(
    "title",
    [
        "Track status derived from OpenF1 race control",
        "Race calendar and identity",
        "HTTP pacing, caching and retries",
        "OpenF1 lap clock and tyre fields",
        "Pit-lane start rule",
        "A plain-language explainer for every phase, kept complete by a test",
    ],
)
def test_source_decisions_exist_by_title(title: str) -> None:
    assert any(t == title for _, t, _ in _entries()), title


def test_stint_plot_conventions_entry_exists_by_title() -> None:
    matches = [body for _, title, body in _entries() if title == "Stint plot conventions"]
    assert len(matches) == 1
    assert "stint-boundary" in matches[0]
    assert "D-15" in matches[0]
