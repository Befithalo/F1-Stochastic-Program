"""FastF1 lap-count fallback and guarded 70-race cache repair tests."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pandas as pd
import pytest

from f1si.data import _db
from f1si.data.loader import (
    ScheduledLapCount,
    backfill_scheduled_laps,
    fetch_fastf1_lap_count,
    resolve_session_lap_count,
)


def _race_rows(*, eligible: int = 70, out_of_sample: int = 2) -> pd.DataFrame:
    rows = []
    for index in range(eligible + out_of_sample):
        year = 2023 + index // 24
        is_oos = index >= eligible
        if is_oos:
            year = 2026
        round_number = (index % 24) + 1
        rows.append(
            {
                "race_id": f"{year}-{round_number:02}",
                "season": year,
                "round": round_number,
                "slug": f"race-{index}",
                "event_name": f"Race {index}",
                "circuit": "Test circuit",
                "country": "Test",
                "race_start_utc": datetime(year, 3, 1),
                "scheduled_laps": None,
                "era": "ground_effect_2022_2025" if not is_oos else "2026",
                "out_of_sample": is_oos,
                "source": "openf1+jolpica",
                "source_version": "test",
                "loaded_at_utc": datetime(2026, 11, 15),
                "load_status": "complete",
            }
        )
    return pd.DataFrame(rows)


def test_session_total_laps_is_preferred_when_fastf1_has_it() -> None:
    session = SimpleNamespace(
        total_laps=57,
        results=pd.DataFrame({"Position": [1], "Laps": [56]}),
    )

    assert resolve_session_lap_count(session) == ScheduledLapCount(57, "FastF1 session total laps")


def test_winner_completed_laps_is_used_when_session_total_is_unavailable() -> None:
    session = SimpleNamespace(
        total_laps=None,
        results=pd.DataFrame({"Position": [2.0, 1.0], "Laps": [57.0, 56.0]}),
    )

    assert resolve_session_lap_count(session) == ScheduledLapCount(
        56, "FastF1 winner completed laps"
    )


def test_fastf1_adapter_loads_race_session_with_cache_and_uses_session_total(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: dict[str, object] = {}

    class Session:
        total_laps = 57
        results = pd.DataFrame({"Position": [1], "Laps": [56]})

        def load(self, **kwargs: bool) -> None:
            calls["load"] = kwargs

    session = Session()
    fake_fastf1 = ModuleType("fastf1")
    fake_fastf1.__dict__["Cache"] = SimpleNamespace(
        configure=lambda **kwargs: calls.update({"cache": kwargs})
    )

    def get_session(*args: object) -> Session:
        calls["session"] = args
        return session

    fake_fastf1.__dict__["get_session"] = get_session
    monkeypatch.setitem(sys.modules, "fastf1", fake_fastf1)

    result = fetch_fastf1_lap_count(2023, 1, tmp_path / "fastf1-cache")

    assert result == ScheduledLapCount(57, "FastF1 session total laps")
    assert calls["session"] == (2023, 1, "R")
    assert calls["load"] == {
        "laps": True,
        "telemetry": False,
        "weather": False,
        "messages": False,
    }
    assert calls["cache"] == {"cache_dir": str((tmp_path / "fastf1-cache").resolve())}


@pytest.mark.parametrize(
    "session",
    [
        SimpleNamespace(total_laps=0, results=pd.DataFrame({"Position": [2], "Laps": [0]})),
        SimpleNamespace(total_laps=0, results=pd.DataFrame({"Position": [2], "Laps": [55]})),
        SimpleNamespace(total_laps=None, results=None),
    ],
)
def test_missing_fastf1_count_and_winner_fail_closed(session: object) -> None:
    with pytest.raises(ValueError, match="FastF1"):
        resolve_session_lap_count(session)


def test_every_eligible_cached_race_has_a_lap_count_and_2026_is_unchanged(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "cache.duckdb"
    _db.write_tables(db_path, {"races": _race_rows()})
    before_oos = _db.read_df(
        db_path,
        "SELECT race_id, scheduled_laps, out_of_sample FROM races "
        "WHERE out_of_sample = TRUE ORDER BY race_id",
    )
    calls: list[tuple[int, int]] = []

    def resolve(season: int, round_number: int, _cache_dir: Path) -> ScheduledLapCount:
        calls.append((season, round_number))
        return ScheduledLapCount(50 + round_number, "FastF1 winner completed laps")

    report = backfill_scheduled_laps(
        db_path,
        fastf1_cache_dir=tmp_path / "fastf1",
        provenance_path=tmp_path / "provenance.csv",
        resolver=resolve,
        echo=lambda _line: None,
    )

    after = _db.read_df(
        db_path,
        "SELECT scheduled_laps FROM races WHERE load_status = 'complete' "
        "AND season BETWEEN 2023 AND 2025 AND out_of_sample = FALSE",
    )
    after_oos = _db.read_df(
        db_path,
        "SELECT race_id, scheduled_laps, out_of_sample FROM races "
        "WHERE out_of_sample = TRUE ORDER BY race_id",
    )
    provenance = pd.read_csv(tmp_path / "provenance.csv")

    assert report.eligible_count == 70
    assert len(report.updated) == 70
    assert report.missing_count == 0
    assert len(calls) == 70
    assert after["scheduled_laps"].gt(0).all()
    pd.testing.assert_frame_equal(before_oos, after_oos)
    assert len(provenance) == 70
    assert set(provenance["source"]) == {"FastF1 winner completed laps"}

    repeated_calls: list[str] = []

    def resolve_existing(_season: int, _round: int, _cache_dir: Path) -> ScheduledLapCount:
        repeated_calls.append("unexpected")
        return ScheduledLapCount(1, "FastF1 session total laps")

    repeated = backfill_scheduled_laps(
        db_path,
        fastf1_cache_dir=tmp_path / "fastf1",
        provenance_path=tmp_path / "provenance.csv",
        resolver=resolve_existing,
        echo=lambda _line: None,
    )
    repeated_provenance = pd.read_csv(tmp_path / "provenance.csv")
    assert repeated.eligible_count == 70
    assert len(repeated.already_valid) == 70
    assert repeated.missing_count == 0
    assert repeated_calls == []
    assert set(repeated_provenance["source"]) == {"FastF1 winner completed laps"}


def test_db_rejects_out_of_sample_and_invalid_scheduled_lap_updates(tmp_path: Path) -> None:
    db_path = tmp_path / "cache.duckdb"
    _db.write_tables(db_path, {"races": _race_rows(eligible=1, out_of_sample=1)})

    with pytest.raises(ValueError, match="eligible complete in-sample"):
        _db.update_scheduled_laps(db_path, "2026-02", 57)
    with pytest.raises(ValueError, match="positive integer"):
        _db.update_scheduled_laps(db_path, "2023-01", 0)
