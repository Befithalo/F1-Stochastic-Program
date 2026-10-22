"""Meta-test (D-02): the planted leaks must be caught, or the guards prove nothing.

* `leaky_consumer.mean_lap_time_whole_race` opens the database directly: caught by BOTH the
  import ban (scan) and the future scramble.
* The through-accessor leaks use only the public door: the import ban sees nothing, only the
  scramble can catch them.
* Every honest consumer passes at a mid-race point.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from f1si.data import _db
from f1si.data.asof import RACE_END, AsOf, AsOfAccessor
from f1si.data.errors import OutOfSampleLockedError, UnknownRaceError
from tests.fixtures import leaky_reexport, leaky_through_accessor
from tests.fixtures.leaky_consumer import mean_lap_time_whole_race
from tests.guards.consumers import CONSUMERS
from tests.guards.import_scan import REPO_ROOT, scan
from tests.guards.scramble import (
    Consumer,
    ConsumerFailed,
    LookaheadDetected,
    assert_no_lookahead,
)

FIXTURES = REPO_ROOT / "tests" / "fixtures"
AT = AsOf("2023-02", 5)


@pytest.fixture(scope="module")
def tables(synthetic_db: Path) -> dict[str, pd.DataFrame]:
    return _db.read_all_tables(synthetic_db)


def test_direct_duckdb_leak_is_caught_by_both_checks(tables: dict[str, pd.DataFrame]) -> None:
    violations = scan([FIXTURES / "leaky_consumer.py"], REPO_ROOT)
    assert violations
    assert any("duckdb" in v.imported for v in violations)
    consumer: Consumer = mean_lap_time_whole_race
    with pytest.raises(LookaheadDetected):
        assert_no_lookahead(consumer, tables, AT, rng=np.random.default_rng(0))


@pytest.mark.parametrize("name", ["lap_plus_three", "race_end_weather", "history_of_next_race"])
def test_through_accessor_leaks_are_caught_only_by_the_scramble(
    tables: dict[str, pd.DataFrame], name: str
) -> None:
    assert scan([FIXTURES / "leaky_through_accessor.py"], REPO_ROOT) == []
    consumer: Consumer = getattr(leaky_through_accessor, name)
    with pytest.raises(LookaheadDetected):
        assert_no_lookahead(consumer, tables, AsOf("2023-02", 2), rng=np.random.default_rng(0))


@pytest.mark.parametrize("name", sorted(CONSUMERS))
def test_honest_consumers_pass(tables: dict[str, pd.DataFrame], name: str) -> None:
    assert_no_lookahead(CONSUMERS[name], tables, AT, rng=np.random.default_rng(0))


@pytest.mark.parametrize("name", ["results_row_count_via_from_import", "laps_via_attribute"])
def test_reexport_leak_is_caught_statically_and_cannot_run(synthetic_db: Path, name: str) -> None:
    """CR-01: a leak through a re-exported private module fails the scan AND fails at runtime."""
    violations = scan([FIXTURES / "leaky_reexport.py"], REPO_ROOT)
    assert any(v.imported in ("f1si.data.asof._db", "f1si.data._db") for v in violations)
    assert not any("duckdb" in v.imported for v in violations)  # no `import duckdb` to rely on
    consumer = getattr(leaky_reexport, name)
    with pytest.raises((ImportError, AttributeError)):
        consumer(synthetic_db, AT)


# WR-01: a consumer that raises proves nothing, so the harness must refuse it


def _always_raises(db_path: Path, at: AsOf) -> object:
    return AsOfAccessor(db_path).snapshot(at).no_such_attribute  # type: ignore[attr-defined]


def _asks_for_a_locked_race(db_path: Path, at: AsOf) -> object:
    return AsOfAccessor(db_path).snapshot(AsOf("2026-01", 1))


def _raises_a_leaky_message(db_path: Path, at: AsOf) -> object:
    """Raises on both runs, with a message that depends on the whole race's weather values."""
    weather = AsOfAccessor(db_path).snapshot(AsOf(at.race_id, RACE_END)).weather
    raise ValueError(f"track temperature total {float(weather['track_temp_c'].sum()):.3f}")


@pytest.mark.parametrize("consumer", [_always_raises, _asks_for_a_locked_race])
def test_a_consumer_that_raises_is_rejected(
    tables: dict[str, pd.DataFrame], consumer: Consumer
) -> None:
    with pytest.raises(ConsumerFailed, match="exercised nothing"):
        assert_no_lookahead(consumer, tables, AT, rng=np.random.default_rng(0))


def test_expected_error_is_asserted_explicitly(tables: dict[str, pd.DataFrame]) -> None:
    assert_no_lookahead(
        _asks_for_a_locked_race,
        tables,
        AT,
        rng=np.random.default_rng(0),
        expect_error=OutOfSampleLockedError,
    )


def test_expected_error_must_be_the_one_raised(tables: dict[str, pd.DataFrame]) -> None:
    with pytest.raises(ConsumerFailed, match="expected UnknownRaceError"):
        assert_no_lookahead(
            _asks_for_a_locked_race,
            tables,
            AT,
            rng=np.random.default_rng(0),
            expect_error=UnknownRaceError,
        )


def test_expected_error_that_never_happens_is_rejected(tables: dict[str, pd.DataFrame]) -> None:
    with pytest.raises(ConsumerFailed, match="got none"):
        assert_no_lookahead(
            CONSUMERS["cars"],
            tables,
            AT,
            rng=np.random.default_rng(0),
            expect_error=OutOfSampleLockedError,
        )


def test_an_expected_error_is_still_compared_between_the_runs(
    tables: dict[str, pd.DataFrame],
) -> None:
    """Both runs raise the expected type, but the message leaks the future: still caught."""
    with pytest.raises(LookaheadDetected):
        assert_no_lookahead(
            _raises_a_leaky_message,
            tables,
            AsOf("2023-02", 2),
            rng=np.random.default_rng(0),
            expect_error=ValueError,
        )
