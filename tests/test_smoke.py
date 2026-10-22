"""Smoke tests: the package imports and the CLI entry point responds."""

import pytest

import f1si
from f1si.cli import main


def test_package_version() -> None:
    assert f1si.__version__ == "0.1.0"


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0
    assert "f1si 0.1.0" in capsys.readouterr().out


def test_help_flag() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
