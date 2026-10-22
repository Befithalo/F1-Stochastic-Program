"""Import-ban guard tests (D-02, DAT-04, FND-03).

The real source tree must be clean, every bypass form must be caught, and the planted leaky
fixture must be flagged. The canary test mirrors the CI canary step on a temporary copy so a
crashed test can never leave a leak in the real `src/` tree.
"""

import ast
import shutil
from pathlib import Path

import pytest

from tests.guards.import_scan import (
    POLICY,
    REPO_ROOT,
    SRC_ROOT,
    format_violations,
    imported_names,
    scan,
    scan_package,
)

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "leaky_consumer.py"

# (path relative to src, source text, flagged?)
SNIPPETS = [
    # flagged
    ("f1si/strategy.py", "import duckdb\n", True),
    ("f1si/strategy.py", "from f1si.data import results\n", True),
    ("f1si/data/sub/x.py", "from .. import _db\n", True),
    ("f1si/x.py", "import importlib\nimportlib.import_module('duckdb')\n", True),
    ("f1si/x.py", "__import__('sqlite3')\n", True),
    ("f1si/x.py", "import random\n", True),
    ("f1si/x.py", "import numpy as np\nnp.random.seed(1)\n", True),
    ("f1si/x.py", "import numpy as np\nnp.random.RandomState(1)\n", True),
    ("f1si/x.py", "import numpy as np\nnp.random.default_rng(1)\n", True),
    ("f1si/x.py", "from numpy.random import default_rng\n", True),
    ("f1si/x.py", "import requests\n", True),
    ("f1si/plots/stints.py", "from f1si.data.sources.openf1 import OpenF1Source\n", True),
    ("f1si/x.py", "from f1si.data.out_of_sample import OutOfSampleAccessor\n", True),
    ("f1si/x.py", "import numpy as np\nnp.random.PCG64(1)\n", True),
    ("f1si/x.py", "from f1si.data import _db\n", True),
    ("f1si/x.py", "from f1si.data._snapshot import snapshot\n", True),
    # allowed
    ("f1si/data/_db.py", "import duckdb\n", False),
    ("f1si/data/asof.py", "from . import _db\n", False),
    ("f1si/rng.py", "import numpy as np\nnp.random.default_rng(1)\n", False),
    ("f1si/data/sources/_http.py", "import requests_cache\n", False),
    ("f1si/cli.py", "from f1si.data.sources import openf1\n", False),
    (
        "f1si/evaluation/holdout.py",
        "from f1si.data.out_of_sample import OutOfSampleAccessor\n",
        False,
    ),
    ("f1si/backtest/scoring.py", "from f1si.data import results\n", False),
    ("f1si/x.py", "import socketserver\n", False),
    ("f1si/x.py", "import numpy.random\n", False),
    ("f1si/x.py", "import numpy as np\nrng = np.random.Generator\n", False),
    ("f1si/x.py", "text = 'import duckdb'\n", False),
]


@pytest.mark.parametrize(("relpath", "source", "flagged"), SNIPPETS)
def test_snippet(tmp_path: Path, relpath: str, source: str, flagged: bool) -> None:
    src_root = tmp_path / "src"
    path = src_root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    violations = scan([path], root=src_root)
    assert bool(violations) is flagged, format_violations(violations)


def test_real_src_tree_is_clean() -> None:
    violations = scan_package()
    assert violations == [], "\n" + format_violations(violations)


def test_policy_has_one_rule_per_protected_name() -> None:
    names = [rule.protected for rule in POLICY]
    assert len(names) == len(set(names))


def test_data_package_init_imports_nothing() -> None:
    tree = ast.parse((SRC_ROOT / "f1si" / "data" / "__init__.py").read_text(encoding="utf-8"))
    assert not [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]


def test_sources_package_init_imports_no_adapter() -> None:
    path = SRC_ROOT / "f1si" / "data" / "sources" / "__init__.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = [name for name, _ in imported_names(tree, "f1si.data.sources", is_pkg=True)]
    banned = (
        "f1si.data.sources._http",
        "f1si.data.sources.openf1",
        "f1si.data.sources.jolpica",
        "f1si.data.sources.synthetic_source",
    )
    assert not [n for n in names if n.startswith(banned)]


def test_no_src_module_imports_tests() -> None:
    offenders: list[str] = []
    for path in sorted((SRC_ROOT / "f1si").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        module = ".".join(path.relative_to(SRC_ROOT).with_suffix("").parts)
        offenders += [
            f"{path}:{lineno} imports {name}"
            for name, lineno in imported_names(tree, module, path.name == "__init__.py")
            if name == "tests" or name.startswith("tests.")
        ]
    assert offenders == []


def test_planted_leak_fixture_is_flagged() -> None:
    violations = scan([FIXTURE], root=REPO_ROOT)
    assert any(v.imported == "duckdb" for v in violations), format_violations(violations)


def test_canary_copy_of_src_tree_is_caught(tmp_path: Path) -> None:
    src_copy = tmp_path / "src"
    shutil.copytree(
        SRC_ROOT / "f1si", src_copy / "f1si", ignore=shutil.ignore_patterns("__pycache__")
    )
    assert scan_package(src_copy) == []
    shutil.copy(FIXTURE, src_copy / "f1si" / "_canary.py")
    violations = scan_package(src_copy)
    assert any(v.module == "f1si._canary" and v.imported == "duckdb" for v in violations), (
        format_violations(violations)
    )
