---
phase: "09"
plan: "03"
subsystem: geometry
tags: [sakhir, provenance, sha256, profile-validation, rights]
status: complete
dependency_graph:
  requires: [09-02 immutable PhysicsInput and versioned artifact reference]
  provides: [fail-closed geometry loader, pinned Sakhir manifest, rights disposition]
  affects: [09-04 parameter sensitivity, Phase 10 point-mass model]
tech_stack:
  added: []
  patterns: [path-confined local asset, digest-before-parse, closed-loop geometry validation]
key_files:
  created:
    - src/f1si/geometry/__init__.py
    - src/f1si/geometry/profile.py
    - docs/geometry/bahrain-2023-profile.json
  modified:
    - tests/geometry/test_profile.py
    - src/f1si/data/physics_input.py
    - DECISIONS.md
    - .planning/phases/09-data-and-geometry-readiness/09-VALIDATION.md
decisions: [DEC-138]
requirements-completed: [GEO-01]
metrics:
  completed_date: 2026-11-17
  upstream_revision: e59595d1f3573b30d1ded6a08984935b957688e0
  raw_sha256: bc3c23da42f9474dbf5700341037bb45521acaa2ad1389bd0a48540fe179ee7a
  asset_bytes_local_ignored: 36718
  centerline_points: 1082
  centerline_distance_m: 5405.749
  seam_distance_m: 5.001
  width_range_m: [5.096, 11.794]
  maximum_curvature_inv_m: 0.100326
  curvature_p95_resample_delta: 0.135194
  curvature_p95_smoothing_delta: 0.098969
  maximum_smoothing_displacement_fraction: 0.119267
  redistribution_status: external_local_only
  focused_tests_passed: 20
actuals:
  tasks: 2
  implementation_commits: 2
---

# Phase 09 Plan 03: Validated Sakhir Geometry Profile

The Phase 10 reference geometry is now a pinned, digest-checked Sakhir profile. The loader confines files beneath the configured geometry root, checks the raw SHA-256 before parsing, validates units and geometry quality, and returns immutable arrays with a `VersionedArtifactRef` that `PhysicsInput` accepts.

## Provenance and Rights

The source is `tracks/Sakhir.csv` at TUMFTM repository commit `e59595d1f3573b30d1ded6a08984935b957688e0`, with SHA-256 `bc3c23da42f9474dbf5700341037bb45521acaa2ad1389bd0a48540fe179ee7a`. The repository marks itself LGPL-3.0. Its README says centerline GPS points came from OpenStreetMap and widths were extracted from satellite images, but it does not name the imagery source or provide a separate license for this CSV. DEC-138 therefore keeps the raw asset at ignored `data/geometry/Sakhir.csv`; only the provenance and results manifest is committed. A fresh checkout without the raw file fails with a clear missing-asset error.

The profile preserves the upstream local Cartesian frame and clockwise direction with an identity transform and meter units. The validator does not repair or smooth the source coordinates; smoothing is used only as a quality sensitivity check.

## Validation Results

| Check | Measured | Recorded limit | Result |
|---|---:|---:|---|
| Closed-loop centerline distance | 5,405.749 m | 4,000–6,500 m | pass |
| Seam distance | 5.001 m | <=6 m | pass |
| Track width | 5.096–11.794 m | 1–30 m | pass |
| Maximum curvature | 0.100326 1/m | <=0.12 1/m | pass |
| p95 curvature delta at 2x resampling | 13.52% | <=25% | pass |
| p95 curvature delta under 3-point smoothing | 9.90% | <=25% | pass |
| Maximum smoothing displacement | 11.93% of median segment | <=50% | pass |

The 1,082-point profile has 1,082 closed-loop segments. Its raw file is 36,718 bytes and remains ignored by Git.

## Verification

- `uv run pytest tests/geometry/test_profile.py -q` — **13 passed**.
- `uv run pytest tests/geometry/test_profile.py tests/data/test_physics_input.py -q` — **20 passed**.
- `uv run ruff check` on geometry, PhysicsInput, and geometry/data integration tests — **passed**.
- Loaded the actual pinned local file with the committed manifest and independently compared all 18 recorded numeric metrics against the loader output — **matched**.
- `git check-ignore -v data/geometry/Sakhir.csv` confirms the raw asset is ignored and is not tracked.

## Task Commits

1. `13fb784` — add the digest-checked profile loader and geometry-to-PhysicsInput integration.
2. `4edf911` — record the pinned source, file-level rights disposition, validation results, and DEC-138.

## Next Plan Readiness

Plan 09-04 can publish evidence-supported effective parameters and clearly labeled assumptions. The geometry artifact identity, rights limitations, and validator outcomes are fixed for downstream model construction.
