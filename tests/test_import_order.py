"""interfaces.py imports RaceState only under TYPE_CHECKING, so no import cycle can form."""

import subprocess
import sys

import pytest


def _run(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", "-c", code], capture_output=True, text=True, check=False
    )


@pytest.mark.parametrize(
    "code",
    ["import f1si.state, f1si.interfaces", "import f1si.interfaces, f1si.state"],
)
def test_both_import_orders_work(code: str) -> None:
    result = _run(code)
    assert result.returncode == 0, result.stderr


def test_interfaces_alone_does_not_load_state() -> None:
    result = _run("import sys, f1si.interfaces; sys.exit(1 if 'f1si.state' in sys.modules else 0)")
    assert result.returncode == 0, result.stderr
