"""AST import scanner: the "around the accessor" half of the look-ahead guard (D-02, DAT-04).

Every race row is meant to reach strategy code only through the as-of door
(`f1si.data.asof`). This module parses source files with `ast` and checks every import against
one policy table, `POLICY`: a protected name (a package, a module, or a numpy.random function)
may only be imported by the modules listed as allowed for it. Matching is by dotted prefix:
an imported name `n` matches protected `p` iff `n == p` or `n` starts with `p + "."`; an importer
`m` is allowed iff `m` equals an allowed name or starts with that name plus ".".

What is detected:
  * `import x` and `from x import y` (relative imports are resolved against the package, and
    `from pkg import name` also yields `pkg.name`, so `from f1si.data import results` is seen);
  * `importlib.import_module("x")`, `import_module("x")` and `__import__("x")` with a string
    literal argument;
  * attribute use of the numpy RNG constructors (`np.random.default_rng`, `RandomState`,
    `np.random.seed`, bit generators), which need no import statement of their own.

Honest limit: Python cannot be sandboxed. `getattr`, `exec` or a computed module name defeat a
static scan. This stops accidents and obvious bypasses; the future-scramble test (plan 01-07)
catches behaviour that the import ban cannot see.
"""

import ast
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
SRC_ROOT: Final = REPO_ROOT / "src"

_EM_DASH: Final = "—"


@dataclass(frozen=True)
class Rule:
    """A protected name and the modules that may import it."""

    protected: str
    allowed: frozenset[str]
    reason: str


@dataclass(frozen=True)
class Violation:
    """One forbidden import found in one module."""

    path: Path
    module: str
    lineno: int
    imported: str
    reason: str


def _rule(protected: str, allowed: tuple[str, ...], reason: str) -> Rule:
    return Rule(protected, frozenset(allowed), reason)


_NETWORK_REASON: Final = "network only through the rate-limited client"
_RNG_CTOR_REASON: Final = "only f1si.rng.make_rng creates generators (FND-03)"

POLICY: Final[tuple[Rule, ...]] = (
    _rule("duckdb", ("f1si.data._db",), "only the storage module opens the database (D-02)"),
    _rule("sqlite3", (), "SQLite files (HTTP cache) are a back door to whole races"),
    _rule("requests", ("f1si.data.sources._http",), _NETWORK_REASON),
    _rule("requests_cache", ("f1si.data.sources._http",), _NETWORK_REASON),
    _rule("urllib.request", ("f1si.data.sources._http",), _NETWORK_REASON),
    _rule("http.client", ("f1si.data.sources._http",), _NETWORK_REASON),
    _rule("socket", ("f1si.data.sources._http",), _NETWORK_REASON),
    _rule("random", (), "stdlib random bypasses the seeded Generator (FND-03)"),
    _rule("numpy.random.RandomState", (), "legacy global RNG (FND-03)"),
    _rule("numpy.random.seed", (), "legacy global RNG (FND-03)"),
    _rule("numpy.random.default_rng", ("f1si.rng",), _RNG_CTOR_REASON),
    _rule("numpy.random.PCG64", ("f1si.rng",), _RNG_CTOR_REASON),
    _rule("numpy.random.Philox", ("f1si.rng",), _RNG_CTOR_REASON),
    _rule("numpy.random.SFC64", ("f1si.rng",), _RNG_CTOR_REASON),
    _rule("numpy.random.MT19937", ("f1si.rng",), _RNG_CTOR_REASON),
    _rule(
        "f1si.data._db",
        (
            "f1si.data.asof",
            "f1si.data._snapshot",
            "f1si.data.results",
            "f1si.data.out_of_sample",
            "f1si.data.loader",
        ),
        "storage is reachable only through the doors and the loader",
    ),
    _rule(
        "f1si.data._snapshot",
        ("f1si.data.asof", "f1si.data.out_of_sample"),
        "snapshot internals are not a door",
    ),
    _rule(
        "f1si.data.results",
        ("f1si.backtest.scoring",),
        "results door: only backtest scoring (D-03)",
    ),
    _rule(
        "f1si.data.out_of_sample",
        ("f1si.evaluation.holdout",),
        "2026 door: only the holdout evaluation (D-04)",
    ),
    _rule(
        "f1si.data.sources._http",
        ("f1si.data.sources.jolpica", "f1si.data.sources.openf1"),
        "HTTP client belongs to the real adapters",
    ),
    _rule(
        "f1si.data.sources.openf1",
        ("f1si.cli",),
        "the CLI chooses the source",
    ),
    _rule(
        "f1si.data.sources.jolpica",
        ("f1si.data.sources.openf1",),
        "Jolpica is part of the OpenF1 source",
    ),
)

_RNG_CONSTRUCTORS: Final = frozenset({"default_rng", "PCG64", "Philox", "SFC64", "MT19937"})


def _matches(name: str, protected: str) -> bool:
    return name == protected or name.startswith(protected + ".")


def module_name_for(path: Path, root: Path) -> tuple[str, bool]:
    """Dotted module name of `path` relative to `root`, and whether it is a package `__init__`."""
    parts = list(path.resolve().relative_to(root.resolve()).with_suffix("").parts)
    is_pkg = parts[-1] == "__init__"
    if is_pkg:
        parts = parts[:-1]
    return ".".join(parts), is_pkg


def imported_names(tree: ast.Module, module: str, is_pkg: bool) -> list[tuple[str, int]]:
    """Every module name the tree imports, with its line number.

    Relative imports are resolved against `module`. `from pkg import name` yields both `pkg` and
    `pkg.name`, because `name` may itself be a submodule.
    """
    out: list[tuple[str, int]] = []
    pkg_parts = module.split(".") if is_pkg else module.split(".")[:-1]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out += [(alias.name, node.lineno) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base_parts = pkg_parts[: len(pkg_parts) - (node.level - 1)] if node.level else []
            base = ".".join([*base_parts, *(node.module.split(".") if node.module else [])])
            out.append((base, node.lineno))
            out += [(f"{base}.{alias.name}", node.lineno) for alias in node.names]
        elif (
            isinstance(node, ast.Call)
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
            and (
                (isinstance(node.func, ast.Attribute) and node.func.attr == "import_module")
                or (
                    isinstance(node.func, ast.Name)
                    and node.func.id in {"import_module", "__import__"}
                )
            )
        ):
            out.append((node.args[0].value, node.lineno))
    return out


def rng_attribute_names(tree: ast.Module, module: str) -> list[tuple[str, int]]:
    """RNG constructors and legacy seeding reached by attribute access (`np.random.seed(...)`)."""
    del module  # the same names are flagged in every module; the policy decides who may use them
    out: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        if node.attr == "RandomState":
            out.append(("numpy.random.RandomState", node.lineno))
        elif (
            node.attr == "seed"
            and isinstance(node.value, ast.Attribute)
            and node.value.attr == "random"
        ):
            out.append(("numpy.random.seed", node.lineno))
        elif node.attr in _RNG_CONSTRUCTORS:
            out.append((f"numpy.random.{node.attr}", node.lineno))
    return out


def _allowed(module: str, rule: Rule) -> bool:
    if rule.protected.startswith("f1si.") and _matches(module, rule.protected):
        return True  # a protected module may import its own submodules
    return any(_matches(module, allowed) for allowed in rule.allowed)


def scan(paths: Iterable[Path], root: Path) -> list[Violation]:
    """Check every file in `paths` (module names are computed relative to `root`)."""
    violations: list[Violation] = []
    for path in paths:
        module, is_pkg = module_name_for(path, root)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        names = imported_names(tree, module, is_pkg) + rng_attribute_names(tree, module)
        for name, lineno in sorted(names, key=lambda item: (item[1], item[0])):
            for rule in POLICY:
                if _matches(name, rule.protected) and not _allowed(module, rule):
                    violations.append(Violation(path, module, lineno, name, rule.reason))
    return violations


def scan_package(src_root: Path = SRC_ROOT) -> list[Violation]:
    """Scan every `*.py` under `src_root / "f1si"`, in sorted order."""
    return scan(sorted((src_root / "f1si").rglob("*.py")), root=src_root)


def format_violations(violations: Iterable[Violation]) -> str:
    """One line per violation: `path:lineno module imports NAME - reason`."""
    return "\n".join(
        f"{v.path}:{v.lineno} {v.module} imports {v.imported} {_EM_DASH} {v.reason}"
        for v in violations
    )
