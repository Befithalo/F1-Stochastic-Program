"""The safety-car estimator ignores the future: scramble test on a database that has SCs."""

from pathlib import Path

import numpy as np
import pytest

from f1si.data import _db
from f1si.data.asof import AsOf
from tests.conftest import SC_HISTORY_CURRENT_RACE_ID
from tests.guards.consumers import CONSUMERS
from tests.guards.scramble import assert_no_lookahead


@pytest.mark.parametrize("lap", [0, 5, 20])
def test_sc_rate_ignores_the_future(sc_history_db: Path, lap: int) -> None:
    tables = _db.read_all_tables(sc_history_db)
    assert_no_lookahead(
        CONSUMERS["sc_rate"],
        tables,
        AsOf(SC_HISTORY_CURRENT_RACE_ID, lap),
        rng=np.random.default_rng(lap),
    )
