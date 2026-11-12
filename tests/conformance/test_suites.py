"""Honest implementations pass; every planted single-defect stub is rejected (D-11, INT-02)."""

from pathlib import Path

import numpy as np
import pytest

from f1si.interfaces import PaceModel
from tests.conformance import stubs
from tests.conformance.registry import (
    PACE_MODELS,
    POLICIES,
    SIMULATORS,
    ConstantPace,
    HoldPolicy,
    NoisySimulator,
    example_state,
)
from tests.conformance.suites import (
    PolicyCase,
    SimCase,
    check_pace_model,
    check_simulator_backend,
    check_strategy_policy,
)

PACE_KEYS = {
    "WrongShapePace": "shape",
    "NanPace": "finite",
    "IntDtypePace": "dtype",
    "ZeroSdPace": "sd",
    "MutatesInputPace": "mutation",
    "NonDeterministicPace": "determinism",
    "MissingPredict": "structure",
}
POLICY_KEYS = {
    "MutatesStatePolicy": "mutation",
    "NonDeterministicPolicy": "determinism",
    "IllegalCompoundPolicy": "legal",
    "WrongReturnPolicy": "return type",
    "MissingDecide": "structure",
}
SIM_KEYS = {
    "WrongShapeSim": "shape",
    "NanSim": "finite",
    "NotPermutationSim": "permutation",
    "IgnoresSeedSim": "reproducible",
    "MissingSimulate": "structure",
}
LEGAL = frozenset({"SOFT", "MEDIUM", "HARD"})


@pytest.mark.parametrize("name", sorted(PACE_MODELS))
def test_honest_pace_models_pass(name: str, long_synthetic_db: Path) -> None:
    model, probe = PACE_MODELS[name](long_synthetic_db)
    check_pace_model(model, probe)


@pytest.mark.parametrize("name", sorted(POLICIES))
def test_honest_policies_pass(name: str, long_synthetic_db: Path) -> None:
    policy, case = POLICIES[name](long_synthetic_db)
    check_strategy_policy(policy, case)


@pytest.mark.parametrize("name", sorted(SIMULATORS))
def test_honest_simulators_pass(name: str, long_synthetic_db: Path) -> None:
    sim, case = SIMULATORS[name](long_synthetic_db)
    check_simulator_backend(sim, case)


@pytest.mark.parametrize("name", sorted(PACE_KEYS))
def test_bad_pace_stub_is_rejected(name: str, long_synthetic_db: Path) -> None:
    _, probe = PACE_MODELS["constant_pace"](long_synthetic_db)
    stub: object = getattr(stubs, name)()
    with pytest.raises(AssertionError, match=f"^{PACE_KEYS[name]}"):
        check_pace_model(stub, probe)


@pytest.mark.parametrize("name", sorted(POLICY_KEYS))
def test_bad_policy_stub_is_rejected(name: str) -> None:
    case = PolicyCase(example_state(), "ALO", LEGAL)
    stub: object = getattr(stubs, name)()
    with pytest.raises(AssertionError, match=f"^{POLICY_KEYS[name]}"):
        check_strategy_policy(stub, case)


@pytest.mark.parametrize("name", sorted(SIM_KEYS))
def test_bad_simulator_stub_is_rejected(name: str) -> None:
    case = SimCase(example_state(), 64)
    stub: object = getattr(stubs, name)()
    with pytest.raises(AssertionError, match=f"^{SIM_KEYS[name]}"):
        check_simulator_backend(stub, case)


def test_stub_tables_cover_every_stub_class() -> None:
    declared = set(PACE_KEYS) | set(POLICY_KEYS) | set(SIM_KEYS)
    defined = {
        n for n, v in vars(stubs).items() if isinstance(v, type) and v.__module__ == stubs.__name__
    }
    assert declared == defined


def test_runtime_checkable_checks_names_only() -> None:
    """A1: right method name with a wrong signature still passes isinstance."""

    class WrongSignature:
        def predict(self, x: int) -> int:
            return x

    assert isinstance(WrongSignature(), PaceModel)


def test_doubles_behave() -> None:
    assert isinstance(ConstantPace(), PaceModel)
    assert HoldPolicy().decide(example_state(), driver="ALO").pit_now is False
    res = NoisySimulator().simulate(example_state(), n_races=3, rng=np.random.default_rng(1))
    assert res.finish_positions.shape == (3, 4)
