"""The results and out-of-sample doors and the 2026 lock (D-03, D-04, DAT-05)."""

import inspect
import types
from pathlib import Path

import pytest

from f1si.data import asof, out_of_sample, results
from f1si.data.asof import RACE_END, AsOf, AsOfAccessor
from f1si.data.errors import OutOfSampleLockedError, UnknownRaceError
from f1si.data.out_of_sample import OutOfSampleAccessor
from f1si.data.results import ResultsAccessor

BAD_PARAM_WORDS = ("include", "unlock", "allow")


def _public_callables(module: types.ModuleType) -> list[object]:
    found: list[object] = []
    for name, obj in vars(module).items():
        if name.startswith("_") or getattr(obj, "__module__", None) != module.__name__:
            continue
        if inspect.isfunction(obj):
            found.append(obj)
        elif inspect.isclass(obj):
            found.extend(
                m for n, m in inspect.getmembers(obj, inspect.isfunction) if not n.startswith("_")
            )
    return found


@pytest.mark.parametrize("module", [asof, results, out_of_sample])
def test_no_flag_parameters_anywhere(module: types.ModuleType) -> None:
    callables = _public_callables(module)
    assert callables
    for fn in callables:
        for param in inspect.signature(fn).parameters:  # type: ignore[arg-type]
            assert not any(word in param for word in BAD_PARAM_WORDS), (fn, param)


def test_as_of_door_locks_2026(synthetic_db: Path) -> None:
    accessor = AsOfAccessor(synthetic_db)
    for call in (
        lambda: accessor.snapshot(AsOf("2026-01", 5)),
        lambda: accessor.snapshot(AsOf("2026-01", RACE_END)),
        lambda: accessor.history(AsOf("2026-01", 0)),
    ):
        with pytest.raises(OutOfSampleLockedError) as err:
            call()
        assert "out-of-sample" in str(err.value)
        assert "f1si.data.out_of_sample" in str(err.value)


def test_history_never_includes_2026(synthetic_db: Path) -> None:
    hist = AsOfAccessor(synthetic_db).history(AsOf("2024-01", 3))
    assert "2026-01" not in hist.races
    assert "2026-01" not in set(hist.results["race_id"])


def test_results_door_final_classification(synthetic_db: Path) -> None:
    df = ResultsAccessor(synthetic_db).final_classification("2023-02")
    assert len(df) == 6
    assert df["driver_code"].tolist()[:5] == ["AAA", "BBB", "CCC", "DDD", "EEE"]
    assert df["final_position"].tolist()[:5] == [1, 2, 3, 4, 5]
    assert df["final_position"].isna().tolist() == [False] * 5 + [True]
    assert df["driver_code"].iloc[-1] == "FFF"


def test_results_door_orders_by_final_position(synthetic_db: Path) -> None:
    df = ResultsAccessor(synthetic_db).final_classification("2023-01")
    assert df["final_position"].tolist() == [1, 2, 3, 4, 5, 6]
    assert df["driver_code"].tolist()[:3] == ["AAA", "CCC", "BBB"]


def test_results_door_locks_2026_and_rejects_unknown(synthetic_db: Path) -> None:
    door = ResultsAccessor(synthetic_db)
    with pytest.raises(OutOfSampleLockedError):
        door.final_classification("2026-01")
    with pytest.raises(UnknownRaceError):
        door.final_classification("1999-01")


def test_out_of_sample_door(synthetic_db: Path) -> None:
    door = OutOfSampleAccessor(synthetic_db)
    snap = door.snapshot(AsOf("2026-01", 5))
    assert snap.cutoff_s is not None
    assert bool((snap.laps["lap_end_s"] <= snap.cutoff_s).all())
    assert sorted(snap.cars["laps_done"].astype(int).tolist()) == [4] * 5 + [5]
    assert len(door.final_classification("2026-01")) == 6
    with pytest.raises(ValueError, match=r"AsOfAccessor"):
        door.snapshot(AsOf("2023-01", 5))
    with pytest.raises(ValueError, match=r"AsOfAccessor"):
        door.final_classification("2023-01")
