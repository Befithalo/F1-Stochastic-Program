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
from f1si.data.asof import AsOf
from tests.fixtures import leaky_reexport, leaky_through_accessor
from tests.fixtures.leaky_consumer import mean_lap_time_whole_race
from tests.guards.consumers import CONSUMERS
from tests.guards.import_scan import REPO_ROOT, scan
from tests.guards.scramble import Consumer, LookaheadDetected, assert_no_lookahead

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
