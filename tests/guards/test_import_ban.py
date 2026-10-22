"""Import-ban guard tests (D-02, DAT-04, FND-03).

The real source tree must be clean, every bypass form must be caught, and the planted leaky
fixture must be flagged. The canary test mirrors the CI canary step on a temporary copy so a
crashed test can never leave a leak in the real `src/` tree.
"""

import ast
import importlib
import pkgutil
import shutil
import types
from pathlib import Path

import pytest

import f1si
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
REEXPORT_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "leaky_reexport.py"

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
    # CR-01: private storage reached through a module that re-exports it
    ("f1si/strategy.py", "from f1si.data.loader import _db\n", True),
    ("f1si/strategy.py", "from f1si.data.asof import _db\n", True),
    ("f1si/strategy.py", "from f1si.data.asof import _snapshot\n", True),
    ("f1si/strategy.py", "from f1si.data.results import _db\n", True),
    ("f1si/strategy.py", "from f1si.data.out_of_sample import _snapshot\n", True),
    ("f1si/strategy.py", "from f1si.data.asof import _db as storage\n", True),
    ("f1si/strategy.py", "import f1si.data.asof as a\na._db.read_df(1, 'x')\n", True),
    ("f1si/strategy.py", "from f1si.data import asof\nasof._db.read_df(1, 'x')\n", True),
    ("f1si/strategy.py", "from f1si.data import asof\nx = asof._snapshot\n", True),
    ("f1si/strategy.py", "import f1si.data.loader\nf1si.data.loader._db\n", True),
    ("f1si/strategy.py", "import f1si.data.asof._db\n", True),
    ("f1si/strategy.py", "def f(m):\n    return m._db.read_df(1, 'x')\n", True),
    ("f1si/strategy.py", "def f(m):\n    return getattr(m, '_db')\n", True),
    ("f1si/x.py", "import importlib\nimportlib.import_module('f1si.data.asof._db')\n", True),
    (
        "f1si/x.py",
        "from importlib import import_module\nimport_module('f1si.data.loader._db')\n",
        True,
    ),
    ("f1si/x.py", "__import__('f1si.data.asof._snapshot')\n", True),
    ("f1si/x.py", "import sys\nm = sys.modules['f1si.data._db']\n", True),
    ("f1si/x.py", "import sys\nm = sys.modules['f1si.data.asof._db']\n", True),
    ("f1si/x.py", "import f1si\nf1si.data._db.read_df(1, 'x')\n", True),
    ("f1si/x.py", "from f1si.data import *\n", True),
    ("f1si/data/sub/x.py", "from ..asof import _db\n", True),
    # WR-11: more RNG forms, alias resolution, SQL engines
    ("f1si/x.py", "from numpy.random import PCG64DXSM\n", True),
    ("f1si/x.py", "from numpy.random import SeedSequence\n", True),
    ("f1si/x.py", "from numpy.random import BitGenerator\n", True),
    ("f1si/x.py", "import numpy as np\nnp.random.PCG64DXSM(1)\n", True),
    ("f1si/x.py", "import numpy as np\nnp.random.SeedSequence(1)\n", True),
    ("f1si/x.py", "from numpy import random as r\nr.seed(1)\n", True),
    ("f1si/x.py", "import numpy.random as r\nr.seed(1)\n", True),
    ("f1si/x.py", "from numpy import random\nrandom.seed(1)\n", True),
    ("f1si/x.py", "from numpy import random as r\nr.default_rng(1)\n", True),
    ("f1si/x.py", "from numpy.random import *\n", True),
    ("f1si/x.py", "import polars\n", True),
    ("f1si/x.py", "import ibis\n", True),
    ("f1si/x.py", "import sqlalchemy\n", True),
    ("f1si/x.py", "import pandas as pd\npd.read_sql('x', 1)\n", True),
    ("f1si/x.py", "from pandas import read_sql_query\n", True),
    # allowed
    (
        "f1si/data/asof.py",
        "def f():\n    from f1si.data import _db\n    _db.read_df(1, 'x')\n",
        False,
    ),
    (
        "f1si/data/loader.py",
        "def f():\n    from f1si.data import _db\n    _db.write_race()\n",
        False,
    ),
    ("f1si/data/out_of_sample.py", "from f1si.data import _db, _snapshot\n", False),
    ("f1si/data/_snapshot.py", "from f1si.data import _db\nx = _db.read_df\n", False),
    ("f1si/x.py", "from f1si.data.asof import AsOfAccessor, RACE_END\n", False),
    ("f1si/x.py", "x = 'f1si.data'\n", False),
    ("f1si/x.py", "x = 'some prose about f1si.data._db in a sentence'\n", False),
    ("f1si/rng.py", "import numpy as np\nnp.random.SeedSequence(1)\n", False),
    ("f1si/x.py", "import numpy as np\nnp.random.Generator\n", False),
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


def test_scan_covers_the_whole_src_tree_not_only_f1si(tmp_path: Path) -> None:
    """A module outside `src/f1si` (WR-11) is scanned too."""
    src_root = tmp_path / "src"
    (src_root / "f1si").mkdir(parents=True)
    (src_root / "f1si" / "__init__.py").write_text("", encoding="utf-8")
    (src_root / "other_pkg").mkdir()
    (src_root / "other_pkg" / "sneaky.py").write_text("import duckdb\n", encoding="utf-8")
    violations = scan_package(src_root)
    assert [v.module for v in violations] == ["other_pkg.sneaky"], format_violations(violations)


# Modules that must never be reachable as an attribute of another module (CR-01).
_PRIVATE_STORAGE_MODULES = frozenset({"duckdb", "sqlite3", "f1si.data._db", "f1si.data._snapshot"})


def _f1si_leaf_modules() -> list[types.ModuleType]:
    """Import every non-package, non-private, non-entry-point module of `f1si`."""
    modules: list[types.ModuleType] = []
    for info in pkgutil.walk_packages(f1si.__path__, "f1si."):
        leaf = info.name.rsplit(".", 1)[-1]
        if info.ispkg or leaf.startswith("_"):
            continue  # packages bind their submodules by design; private modules are internal
        modules.append(importlib.import_module(info.name))
    return modules


def test_no_public_module_re_exports_private_storage() -> None:
    """Runtime half of CR-01: `from f1si.data.asof import _db` must not even be possible."""
    modules = _f1si_leaf_modules()
    assert {m.__name__ for m in modules} >= {
        "f1si.data.asof",
        "f1si.data.loader",
        "f1si.data.results",
        "f1si.data.out_of_sample",
    }
    leaks = [
        f"{module.__name__}.{attr} is the module {value.__name__}"
        for module in modules
        for attr, value in vars(module).items()
        if isinstance(value, types.ModuleType) and value.__name__ in _PRIVATE_STORAGE_MODULES
    ]
    assert leaks == []


@pytest.mark.parametrize("name", ["asof", "loader", "results", "out_of_sample"])
def test_door_modules_have_no_private_attributes(name: str) -> None:
    module = importlib.import_module(f"f1si.data.{name}")
    for attr in ("_db", "_snapshot", "duckdb"):
        assert not hasattr(module, attr), f"f1si.data.{name} exposes {attr}"


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


def test_canary_reexport_leak_is_caught_in_a_copy_of_src(tmp_path: Path) -> None:
    """The re-export fixture (no `import duckdb` anywhere) must also fail the scan (CR-01)."""
    src_copy = tmp_path / "src"
    shutil.copytree(
        SRC_ROOT / "f1si", src_copy / "f1si", ignore=shutil.ignore_patterns("__pycache__")
    )
    shutil.copy(REEXPORT_FIXTURE, src_copy / "f1si" / "_canary.py")
    violations = scan_package(src_copy)
    imported = {v.imported for v in violations if v.module == "f1si._canary"}
    assert "f1si.data.asof._db" in imported, format_violations(violations)
    assert "f1si.data._db" in imported, format_violations(violations)  # the `x._db` attribute
    assert not any(v.imported == "duckdb" for v in violations)
