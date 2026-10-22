"""Normalized schema: validation, normalization, visibility and DDL."""

from collections.abc import Callable

import pandas as pd
import pytest

from f1si.data import schema
from f1si.data.sources import NormalizedRace
from tests.data.mini_race import mini_entries, mini_laps, mini_race, mini_race_row, mini_ref


def _with_tables(**overrides: pd.DataFrame | None) -> NormalizedRace:
    tables = dict(mini_race().tables)
    for name, df in overrides.items():
        if df is None:
            del tables[name]
        else:
            tables[name] = df
    return NormalizedRace(ref=mini_ref(), tables=tables)


def test_mini_race_is_valid() -> None:
    assert schema.validate_race(mini_race()) == []


def test_tables_are_exactly_the_skeleton_tables() -> None:
    assert list(schema.TABLES) == ["races", "entries", "laps"]
    assert schema.PER_RACE_TABLES == ("entries", "laps")
    assert set(schema.VIEWS) == {"stints", "pit_stops"}


def _drop_column(df: pd.DataFrame) -> pd.DataFrame:
    return df.drop(columns=["lap_time_s"])


def _duplicate_key(df: pd.DataFrame) -> pd.DataFrame:
    return pd.concat([df, df.iloc[[0]]], ignore_index=True)


def _lap_zero(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.loc[0, "lap_number"] = 0
    return out


def _unknown_driver(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.loc[0, "driver_number"] = 99
    return out


def _backwards(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.loc[1, "lap_end_s"] = 50.0
    return out


def _other_race(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["race_id"] = "2023-02"
    return out


@pytest.mark.parametrize(
    ("mutate", "fragment"),
    [
        (_drop_column, "missing column"),
        (_duplicate_key, "duplicate key"),
        (_lap_zero, "lap_number < 1"),
        (_unknown_driver, "not in entries"),
        (_backwards, "ending before they start"),
        (_other_race, "different from"),
    ],
)
def test_validate_reports_each_problem(
    mutate: Callable[[pd.DataFrame], pd.DataFrame], fragment: str
) -> None:
    problems = schema.validate_race(_with_tables(laps=mutate(mini_laps())))
    assert any(fragment in p for p in problems), problems


def test_validate_reports_missing_table() -> None:
    problems = schema.validate_race(_with_tables(laps=None))
    assert any("missing required table 'laps'" in p for p in problems), problems


def test_normalize_raises_keyerror_naming_missing_column() -> None:
    with pytest.raises(KeyError, match="lap_time_s"):
        schema.normalize("laps", mini_laps().drop(columns=["lap_time_s"]))


def test_normalize_casts_to_canonical_dtypes() -> None:
    out = schema.normalize("laps", mini_laps())
    assert list(out.columns) == list(schema.TABLES["laps"].column_names)
    assert str(out["driver_number"].dtype) == "Int64"
    assert str(out["lap_end_s"].dtype) == "Float64"
    assert str(out["is_pit_in_lap"].dtype) == "boolean"
    assert out["compound"].dtype == object
    assert out["lap_end_s"].isna().sum() == 1  # NaN became NA
    assert out["track_status"].isna().all()

    races = schema.normalize("races", pd.DataFrame(_race_row_dict()))
    assert str(races["race_start_utc"].dtype) == "datetime64[us]"
    assert races["race_start_utc"].dt.tz is None


def _race_row_dict() -> dict[str, list[object]]:
    return {str(k): [v] for k, v in mini_race_row().iloc[0].to_dict().items()}


def test_normalize_strips_timezone_as_utc() -> None:
    row = pd.DataFrame(_race_row_dict())
    row["race_start_utc"] = pd.to_datetime(["2023-03-05T17:00:00+02:00"])
    out = schema.normalize("races", row)
    assert out["race_start_utc"].iloc[0] == pd.Timestamp("2023-03-05T15:00:00")


def test_add_visibility_copies_lap_end_and_leaves_entries_alone() -> None:
    laps = schema.add_visibility("laps", mini_laps())
    pd.testing.assert_series_equal(laps["visible_at_s"], laps["lap_end_s"], check_names=False)
    entries = mini_entries()
    assert schema.add_visibility("entries", entries) is entries


def test_ddl_marks_required_columns_and_has_no_primary_key() -> None:
    sql = schema.ddl("laps")
    assert "driver_number INTEGER NOT NULL" in sql
    assert "lap_end_s DOUBLE," in sql
    assert "PRIMARY KEY" not in sql
    assert sql.startswith("CREATE TABLE IF NOT EXISTS laps")
