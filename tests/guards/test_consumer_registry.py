"""Consumer registration is enforced by tests, not by convention (WR-02).

The future-scramble test only covers functions listed in `CONSUMERS`. These tests make forgetting
to register one a failure: every public function of a designated consumer module must be consumed
or exempt (with a reason), and only the replay drivers may hold the accessor at all.
"""

import ast
import importlib
import inspect
from types import ModuleType

import pytest

from tests.guards.consumers import CONSUMED, CONSUMERS, DESIGNATED_MODULES, EXEMPT
from tests.guards.import_scan import SRC_ROOT, module_name_for


def _public_callables(module: ModuleType) -> set[str]:
    """Qualified names of public functions defined in `module` and public methods of its classes."""
    found: set[str] = set()
    for name, member in vars(module).items():
        if name.startswith("_") or getattr(member, "__module__", None) != module.__name__:
            continue
        if inspect.isfunction(member):
            found.add(f"{module.__name__}.{name}")
        elif inspect.isclass(member):
            found |= {
                f"{module.__name__}.{name}.{method}"
                for method, value in vars(member).items()
                if not method.startswith("_") and inspect.isfunction(value)
            }
    return found


def test_every_public_function_is_consumed_or_exempt() -> None:
    found: set[str] = set()
    for name in DESIGNATED_MODULES:
        found |= _public_callables(importlib.import_module(name))
    declared = set(CONSUMED) | set(EXEMPT)
    assert found - declared == set(), "register a consumer or exempt it with a reason"
    assert declared - found == set(), "stale entry: the function no longer exists"
    assert not set(CONSUMED) & set(EXEMPT)


def test_exemptions_carry_a_reason() -> None:
    assert all(len(reason.split()) >= 4 for reason in EXEMPT.values())


@pytest.mark.parametrize(("qualified", "consumer"), sorted(CONSUMED.items()))
def test_consumed_function_is_really_called_by_its_consumer(qualified: str, consumer: str) -> None:
    assert consumer in CONSUMERS, f"{consumer!r} is not registered in CONSUMERS"
    called = qualified.rsplit(".", 1)[-1]
    assert called in CONSUMERS[consumer].__code__.co_names, (
        f"consumer {consumer!r} never calls {called}"
    )


def test_only_the_drivers_name_the_accessor_in_src() -> None:
    """No model or plot module may hold an AsOfAccessor or ask for RACE_END."""
    users: set[str] = set()
    for path in sorted(SRC_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        module, _ = module_name_for(path, SRC_ROOT)
        for node in ast.walk(tree):
            names: set[str] = set()
            if isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
            elif isinstance(node, ast.ImportFrom | ast.Import):
                names |= {alias.name.rsplit(".", 1)[-1] for alias in node.names}
            if names & {"AsOfAccessor", "RACE_END", "RaceEnd"}:
                users.add(module)
    assert users <= {"f1si.cli", "f1si.data.asof", "f1si.data._snapshot"}, sorted(users)


def test_the_registry_check_sees_a_new_public_function() -> None:
    """Self-test: a function added to a designated module shows up as unregistered."""
    module = ModuleType("f1si.plots.fake")

    def brand_new(snapshot: object) -> object:
        return snapshot

    brand_new.__module__ = module.__name__
    module.brand_new = brand_new  # type: ignore[attr-defined]
    assert _public_callables(module) == {"f1si.plots.fake.brand_new"}
    assert "f1si.plots.fake.brand_new" not in set(CONSUMED) | set(EXEMPT)
