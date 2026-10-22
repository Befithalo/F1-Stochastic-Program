"""Seeded synthetic races with known ground truth (D-09)."""

from f1si.synthetic.generator import (
    SyntheticRace,
    SyntheticRaceSpec,
    SyntheticTruth,
    default_specs,
    generate_dataset,
    generate_race,
)

__all__ = [
    "SyntheticRace",
    "SyntheticRaceSpec",
    "SyntheticTruth",
    "default_specs",
    "generate_dataset",
    "generate_race",
]
