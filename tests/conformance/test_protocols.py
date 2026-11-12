"""mypy proof: conformers are accepted, wrong-signature stubs are rejected (INT-01, D-11).

Each `# type: ignore[arg-type]` below is the proof of rejection. Under mypy strict an unused
ignore is an error, so if mypy ever accepted one of these stubs, `uv run mypy` would fail.
"""

from f1si.interfaces import PaceModel, SimulatorBackend, StrategyPolicy
from tests.conformance.registry import ConstantPace, HoldPolicy, NoisySimulator


class BadPaceSignature:
    def predict(self, drivers: list[int]) -> list[float]:
        return [float(d) for d in drivers]


class BadPolicySignature:
    def decide(self, state: int) -> str:
        return str(state)


class BadSimulatorSignature:
    def simulate(self) -> None:
        return None


class NoMethods:
    pass


def _needs_pace_model(model: PaceModel) -> None:
    return None


def _needs_policy(policy: StrategyPolicy) -> None:
    return None


def _needs_simulator(sim: SimulatorBackend) -> None:
    return None


def test_conformers_accepted_and_wrong_signatures_rejected_by_mypy() -> None:
    _needs_pace_model(ConstantPace())
    _needs_policy(HoldPolicy())
    _needs_simulator(NoisySimulator())
    _needs_pace_model(BadPaceSignature())  # type: ignore[arg-type]
    _needs_pace_model(NoMethods())  # type: ignore[arg-type]
    _needs_policy(BadPolicySignature())  # type: ignore[arg-type]
    _needs_simulator(BadSimulatorSignature())  # type: ignore[arg-type]
