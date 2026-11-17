"""Fail-closed loader for versioned local track profiles (GEO-01)."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any

import numpy as np

from f1si.data.physics_input import VersionedArtifactRef

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_REVISION = re.compile(r"^[0-9a-f]{40}$")
_DEFAULT_MINIMUM_SEGMENT_M = 0.1
_DEFAULT_CURVATURE_STABILITY_DELTA = 0.25


class GeometryProfileError(ValueError):
    """The manifest, source bytes, or geometry quality failed validation."""


@dataclass(frozen=True)
class GeometryProfileManifest:
    """Provenance and thresholds that identify one exact profile artifact."""

    schema_version: int
    profile_id: str
    source_revision: str
    source_asset_path: str
    asset_path: str
    sha256: str
    coordinate_frame: str
    transform: MappingProxyType
    units: MappingProxyType
    attribution: str
    redistribution_status: str
    quality: MappingProxyType
    source_repository: str
    rights_review: MappingProxyType
    validation: MappingProxyType

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible copy, including rights and measured validation outcomes."""
        return {
            "schema_version": self.schema_version,
            "profile_id": self.profile_id,
            "source_repository": self.source_repository,
            "source_revision": self.source_revision,
            "source_asset_path": self.source_asset_path,
            "asset_path": self.asset_path,
            "sha256": self.sha256,
            "coordinate_frame": self.coordinate_frame,
            "transform": _thaw(self.transform),
            "units": _thaw(self.units),
            "attribution": self.attribution,
            "redistribution_status": self.redistribution_status,
            "rights_review": _thaw(self.rights_review),
            "quality": _thaw(self.quality),
            "validation": _thaw(self.validation),
        }


@dataclass(frozen=True)
class GeometryValidation:
    """Measured geometry properties produced by the loader's recorded checks."""

    point_count: int
    segment_count: int
    orientation: str
    total_distance_m: float
    seam_distance_m: float
    minimum_segment_m: float
    median_segment_m: float
    maximum_segment_m: float
    minimum_width_m: float
    maximum_width_m: float
    maximum_curvature_inv_m: float
    curvature_p95_inv_m: float
    resampled_curvature_p95_inv_m: float
    resampled_curvature_relative_delta: float
    smoothed_curvature_p95_inv_m: float
    smoothed_curvature_relative_delta: float
    maximum_smoothing_displacement_m: float
    maximum_smoothing_displacement_fraction: float

    def to_dict(self) -> dict[str, Any]:
        """Return the validation metrics as JSON-compatible scalar values."""
        return {
            "point_count": self.point_count,
            "segment_count": self.segment_count,
            "orientation": self.orientation,
            "total_distance_m": self.total_distance_m,
            "seam_distance_m": self.seam_distance_m,
            "minimum_segment_m": self.minimum_segment_m,
            "median_segment_m": self.median_segment_m,
            "maximum_segment_m": self.maximum_segment_m,
            "minimum_width_m": self.minimum_width_m,
            "maximum_width_m": self.maximum_width_m,
            "maximum_curvature_inv_m": self.maximum_curvature_inv_m,
            "curvature_p95_inv_m": self.curvature_p95_inv_m,
            "resampled_curvature_p95_inv_m": self.resampled_curvature_p95_inv_m,
            "resampled_curvature_relative_delta": self.resampled_curvature_relative_delta,
            "smoothed_curvature_p95_inv_m": self.smoothed_curvature_p95_inv_m,
            "smoothed_curvature_relative_delta": self.smoothed_curvature_relative_delta,
            "maximum_smoothing_displacement_m": self.maximum_smoothing_displacement_m,
            "maximum_smoothing_displacement_fraction": self.maximum_smoothing_displacement_fraction,
        }


@dataclass(frozen=True, eq=False, init=False)
class GeometryProfile:
    """Immutable validated points, widths, provenance, and precomputed quality results."""

    manifest: GeometryProfileManifest
    validation: GeometryValidation
    _x_m: np.ndarray
    _y_m: np.ndarray
    _width_right_m: np.ndarray
    _width_left_m: np.ndarray

    def __init__(
        self,
        manifest: GeometryProfileManifest,
        validation: GeometryValidation,
        x_m: np.ndarray,
        y_m: np.ndarray,
        width_right_m: np.ndarray,
        width_left_m: np.ndarray,
    ) -> None:
        object.__setattr__(self, "manifest", manifest)
        object.__setattr__(self, "validation", validation)
        object.__setattr__(self, "_x_m", _read_only_array(x_m))
        object.__setattr__(self, "_y_m", _read_only_array(y_m))
        object.__setattr__(self, "_width_right_m", _read_only_array(width_right_m))
        object.__setattr__(self, "_width_left_m", _read_only_array(width_left_m))

    @property
    def reference(self) -> VersionedArtifactRef:
        """The digest-pinned handle consumed by PhysicsInput."""
        return VersionedArtifactRef(
            name=self.manifest.profile_id,
            version=self.manifest.source_revision,
            sha256=self.manifest.sha256,
        )

    @property
    def x_m(self) -> np.ndarray:
        """Read-only transformed centerline x coordinates."""
        return self._x_m

    @property
    def y_m(self) -> np.ndarray:
        """Read-only transformed centerline y coordinates."""
        return self._y_m

    @property
    def width_right_m(self) -> np.ndarray:
        """Read-only track width to the right of the supplied centerline direction."""
        return self._width_right_m

    @property
    def width_left_m(self) -> np.ndarray:
        """Read-only track width to the left of the supplied centerline direction."""
        return self._width_left_m

    @property
    def total_distance_m(self) -> float:
        """Closed-loop centerline distance in meters."""
        return self.validation.total_distance_m


def _read_only_array(values: np.ndarray) -> np.ndarray:
    """Back an ndarray with immutable bytes so callers cannot re-enable writes."""
    array = np.asarray(values, dtype="<f8")
    return np.frombuffer(array.tobytes(order="C"), dtype="<f8")


def _mapping(value: object, name: str) -> MappingProxyType:
    if not isinstance(value, dict):
        raise GeometryProfileError(f"manifest {name} must be a JSON object")
    return _freeze(value)


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, MappingProxyType):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _manifest(data: object) -> GeometryProfileManifest:
    if not isinstance(data, dict):
        raise GeometryProfileError("manifest root must be a JSON object")
    try:
        schema_version = int(data["schema_version"])
        profile_id = str(data["profile_id"])
        source_revision = str(data["source_revision"]).lower()
        source_asset_path = str(data["source_asset_path"])
        asset_path = str(data["asset_path"])
        sha256 = str(data["sha256"]).lower()
        coordinate_frame = str(data["coordinate_frame"])
        transform = _mapping(data["transform"], "transform")
        units = _mapping(data["units"], "units")
        attribution = str(data["attribution"])
        redistribution_status = str(data["redistribution_status"])
        quality = _mapping(data["quality"], "quality")
        source_repository = str(data.get("source_repository", ""))
        rights_review = _mapping(data.get("rights_review", {}), "rights_review")
        validation = _mapping(data.get("validation", {}), "validation")
    except (KeyError, TypeError, ValueError) as error:
        raise GeometryProfileError(
            f"manifest is missing or mistypes a required field: {error}"
        ) from error

    if schema_version != 1:
        raise GeometryProfileError(f"unsupported geometry manifest schema version {schema_version}")
    if not profile_id.strip():
        raise GeometryProfileError("profile_id must be non-empty")
    if not _GIT_REVISION.fullmatch(source_revision):
        raise GeometryProfileError("source_revision must be a full 40-character git commit")
    if not _SHA256.fullmatch(sha256):
        raise GeometryProfileError("sha256 must be 64 lowercase hexadecimal characters")
    for field_name, path_value in (
        ("source_asset_path", source_asset_path),
        ("asset_path", asset_path),
    ):
        path = PurePosixPath(path_value)
        if not path_value or path.is_absolute() or ".." in path.parts:
            raise GeometryProfileError(f"manifest {field_name} must be a safe relative path")
    if coordinate_frame != "local_cartesian_xy":
        raise GeometryProfileError("coordinate_frame must be local_cartesian_xy")
    if units.get("coordinates") != "m" or units.get("width") != "m":
        raise GeometryProfileError("profile coordinates and widths must use meters")
    if not attribution.strip():
        raise GeometryProfileError("asset attribution must be recorded")
    if redistribution_status not in {"external_local_only", "redistribution_verified"}:
        raise GeometryProfileError(
            "redistribution_status must state an explicit rights disposition"
        )
    _validate_transform(transform)
    _validate_quality(quality)
    return GeometryProfileManifest(
        schema_version=schema_version,
        profile_id=profile_id,
        source_revision=source_revision,
        source_asset_path=source_asset_path,
        asset_path=asset_path,
        sha256=sha256,
        coordinate_frame=coordinate_frame,
        transform=transform,
        units=units,
        attribution=attribution,
        redistribution_status=redistribution_status,
        quality=quality,
        source_repository=source_repository,
        rights_review=rights_review,
        validation=validation,
    )


def _number(mapping: MappingProxyType, name: str) -> float:
    try:
        value = float(mapping[name])
    except (KeyError, TypeError, ValueError):
        raise GeometryProfileError(f"quality threshold {name!r} must be numeric") from None
    if not math.isfinite(value):
        raise GeometryProfileError(f"quality threshold {name!r} must be finite")
    return value


def _validate_quality(quality: MappingProxyType) -> None:
    names = (
        "minimum_width_m",
        "maximum_width_m",
        "minimum_distance_m",
        "maximum_distance_m",
        "closed_loop_tolerance_m",
        "maximum_curvature_inv_m",
    )
    values = {name: _number(quality, name) for name in names}
    if values["minimum_width_m"] <= 0 or values["maximum_width_m"] <= values["minimum_width_m"]:
        raise GeometryProfileError("width thresholds must be positive and ordered")
    if (
        values["minimum_distance_m"] <= 0
        or values["maximum_distance_m"] <= values["minimum_distance_m"]
    ):
        raise GeometryProfileError("distance thresholds must be positive and ordered")
    if values["closed_loop_tolerance_m"] <= 0 or values["maximum_curvature_inv_m"] <= 0:
        raise GeometryProfileError("loop and curvature thresholds must be positive")
    minimum_segment = float(quality.get("minimum_segment_m", _DEFAULT_MINIMUM_SEGMENT_M))
    if not math.isfinite(minimum_segment) or minimum_segment <= 0:
        raise GeometryProfileError("minimum_segment_m must be finite and positive")
    for name in (
        "maximum_curvature_resample_relative_delta",
        "maximum_curvature_smoothing_relative_delta",
        "maximum_smoothing_displacement_fraction",
    ):
        tolerance = float(quality.get(name, _DEFAULT_CURVATURE_STABILITY_DELTA))
        if not math.isfinite(tolerance) or tolerance <= 0 or tolerance > 2:
            raise GeometryProfileError(f"{name} must be finite and between 0 and 2")


def _validate_transform(transform: MappingProxyType) -> None:
    kind = transform.get("type")
    if kind not in {"identity", "rigid_2d"}:
        raise GeometryProfileError("transform.type must be identity or rigid_2d")
    try:
        translation = np.asarray(transform.get("translation_m"), dtype="float64")
        rotation_deg = float(transform.get("rotation_deg"))
    except (TypeError, ValueError):
        raise GeometryProfileError(
            "transform requires a finite 2D translation and rotation"
        ) from None
    if (
        translation.shape != (2,)
        or not np.isfinite(translation).all()
        or not math.isfinite(rotation_deg)
    ):
        raise GeometryProfileError("transform requires a finite 2D translation and rotation")
    if kind == "identity" and (not np.allclose(translation, 0.0) or rotation_deg != 0.0):
        raise GeometryProfileError("identity transform must have zero translation and rotation")


def _parse_csv(raw: bytes) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    try:
        text = raw.decode("utf-8-sig")
        rows = [
            row
            for row in csv.reader(io.StringIO(text))
            if row and any(cell.strip() for cell in row)
        ]
    except (UnicodeDecodeError, csv.Error) as error:
        raise GeometryProfileError(f"geometry CSV cannot be decoded: {error}") from error
    if not rows:
        raise GeometryProfileError("geometry CSV is empty")

    has_header = False
    try:
        float(rows[0][0])
    except (ValueError, IndexError):
        has_header = True
    if has_header:
        header = [name.strip().lstrip("#").strip().lower() for name in rows.pop(0)]
        if len(set(header)) != len(header):
            raise GeometryProfileError("geometry CSV header contains duplicate columns")
        try:
            x_index = header.index("x_m")
            y_index = header.index("y_m")
            if len(header) == 3 and "width_m" in header:
                right_index = left_index = header.index("width_m")
            else:
                right_index = header.index("w_tr_right_m")
                left_index = header.index("w_tr_left_m")
        except ValueError:
            raise GeometryProfileError(
                "geometry CSV header must identify x, y, and track widths"
            ) from None
        indices = (x_index, y_index, right_index, left_index)
    else:
        if len(rows[0]) == 3:
            indices = (0, 1, 2, 2)
        elif len(rows[0]) == 4:
            indices = (0, 1, 2, 3)
        else:
            raise GeometryProfileError("geometry CSV rows must have three or four numeric columns")

    parsed: list[tuple[float, float, float, float]] = []
    expected_length = len(rows[0])
    for line_number, row in enumerate(rows, start=2 if has_header else 1):
        if len(row) != expected_length:
            raise GeometryProfileError(
                f"geometry CSV row {line_number} has an inconsistent column count"
            )
        try:
            parsed.append(tuple(float(row[index].strip()) for index in indices))
        except (IndexError, ValueError):
            raise GeometryProfileError(
                f"geometry CSV row {line_number} contains a non-numeric value"
            ) from None
    values = np.asarray(parsed, dtype="float64")
    if values.ndim != 2 or values.shape[0] < 8 or not np.isfinite(values).all():
        raise GeometryProfileError("geometry must contain at least eight finite points and widths")
    return values[:, 0], values[:, 1], values[:, 2], values[:, 3]


def _curvature(xy: np.ndarray) -> np.ndarray:
    """Absolute three-point circumcircle curvature for a closed polyline."""
    previous = xy - np.roll(xy, 1, axis=0)
    following = np.roll(xy, -1, axis=0) - xy
    chord = np.roll(xy, -1, axis=0) - np.roll(xy, 1, axis=0)
    denominator = (
        np.linalg.norm(previous, axis=1)
        * np.linalg.norm(following, axis=1)
        * np.linalg.norm(chord, axis=1)
    )
    cross = np.abs(previous[:, 0] * following[:, 1] - previous[:, 1] * following[:, 0])
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.divide(
            2.0 * cross, denominator, out=np.full_like(cross, np.inf), where=denominator > 0
        )


def _relative_delta(reference: float, observed: float) -> float:
    return abs(observed - reference) / max(abs(reference), 1e-12)


def _apply_transform(
    x_m: np.ndarray, y_m: np.ndarray, transform: MappingProxyType
) -> tuple[np.ndarray, np.ndarray]:
    translation = np.asarray(transform["translation_m"], dtype="float64")
    angle = math.radians(float(transform["rotation_deg"]))
    cosine, sine = math.cos(angle), math.sin(angle)
    x_out = cosine * x_m - sine * y_m + translation[0]
    y_out = sine * x_m + cosine * y_m + translation[1]
    return x_out, y_out


def _validate_geometry(
    x_m: np.ndarray,
    y_m: np.ndarray,
    width_right_m: np.ndarray,
    width_left_m: np.ndarray,
    quality: MappingProxyType,
) -> GeometryValidation:
    xy = np.column_stack((x_m, y_m))
    if (
        not np.isfinite(xy).all()
        or not np.isfinite(width_right_m).all()
        or not np.isfinite(width_left_m).all()
    ):
        raise GeometryProfileError("geometry coordinates and widths must be finite")
    widths = np.concatenate((width_right_m, width_left_m))
    minimum_width = float(widths.min())
    maximum_width = float(widths.max())
    minimum_width_limit = _number(quality, "minimum_width_m")
    maximum_width_limit = _number(quality, "maximum_width_m")
    if minimum_width < minimum_width_limit or maximum_width > maximum_width_limit:
        raise GeometryProfileError(
            f"track widths {minimum_width:.3f}..{maximum_width:.3f} m are outside recorded limits"
        )

    seam_distance = float(np.linalg.norm(xy[0] - xy[-1]))
    seam_tolerance = _number(quality, "closed_loop_tolerance_m")
    if seam_distance > seam_tolerance:
        raise GeometryProfileError(
            f"profile is not a closed loop: seam {seam_distance:.3f} m exceeds "
            f"{seam_tolerance:.3f} m"
        )
    minimum_segment_limit = float(quality.get("minimum_segment_m", _DEFAULT_MINIMUM_SEGMENT_M))
    closed_by_duplicate_endpoint = seam_distance <= minimum_segment_limit
    core = xy[:-1] if closed_by_duplicate_endpoint else xy
    segments = np.linalg.norm(np.diff(xy, axis=0), axis=1)
    if closed_by_duplicate_endpoint:
        total_distance = float(segments.sum())
    else:
        segments = np.append(segments, seam_distance)
        total_distance = float(segments.sum())
    minimum_segment = float(segments.min())
    maximum_segment = float(segments.max())
    median_segment = float(np.median(segments))
    if minimum_segment < minimum_segment_limit:
        raise GeometryProfileError(
            f"profile has a degenerate segment of {minimum_segment:.6f} m "
            f"(minimum {minimum_segment_limit:.6f} m)"
        )

    minimum_distance = _number(quality, "minimum_distance_m")
    maximum_distance = _number(quality, "maximum_distance_m")
    if not minimum_distance <= total_distance <= maximum_distance:
        raise GeometryProfileError(
            f"centerline distance {total_distance:.3f} m is outside recorded limits"
        )
    signed_area = float(
        0.5 * np.sum(core[:, 0] * np.roll(core[:, 1], -1) - np.roll(core[:, 0], -1) * core[:, 1])
    )
    if not math.isfinite(signed_area) or abs(signed_area) < 1.0:
        raise GeometryProfileError("centerline direction/order is degenerate")
    orientation = "counterclockwise" if signed_area > 0 else "clockwise"

    raw_curvature = _curvature(core)
    maximum_curvature = float(raw_curvature.max())
    curvature_p95 = float(np.quantile(raw_curvature, 0.95))
    maximum_curvature_limit = _number(quality, "maximum_curvature_inv_m")
    if maximum_curvature > maximum_curvature_limit:
        raise GeometryProfileError(
            f"maximum curvature {maximum_curvature:.6f} 1/m exceeds "
            f"{maximum_curvature_limit:.6f} 1/m"
        )

    resampled = core[::2]
    resampled_curvature = _curvature(resampled)
    resampled_p95 = float(np.quantile(resampled_curvature, 0.95))
    resampled_delta = _relative_delta(curvature_p95, resampled_p95)
    resampled_limit = float(
        quality.get("maximum_curvature_resample_relative_delta", _DEFAULT_CURVATURE_STABILITY_DELTA)
    )
    if resampled_delta > resampled_limit:
        raise GeometryProfileError(
            f"p95 curvature changes {resampled_delta:.1%} under 2x resampling "
            f"(limit {resampled_limit:.1%})"
        )

    smoothed = (np.roll(core, 1, axis=0) + 2.0 * core + np.roll(core, -1, axis=0)) / 4.0
    smoothing_displacement = np.linalg.norm(smoothed - core, axis=1)
    maximum_smoothing_displacement = float(smoothing_displacement.max())
    maximum_smoothing_displacement_fraction = maximum_smoothing_displacement / median_segment
    smoothing_displacement_limit = float(
        quality.get("maximum_smoothing_displacement_fraction", 0.5)
    )
    if maximum_smoothing_displacement_fraction > smoothing_displacement_limit:
        raise GeometryProfileError(
            f"maximum 3-point smoothing displacement is "
            f"{maximum_smoothing_displacement_fraction:.1%} of median segment "
            f"(limit {smoothing_displacement_limit:.1%})"
        )
    smoothed_curvature = _curvature(smoothed)
    smoothed_p95 = float(np.quantile(smoothed_curvature, 0.95))
    smoothed_delta = _relative_delta(curvature_p95, smoothed_p95)
    smoothing_limit = float(
        quality.get(
            "maximum_curvature_smoothing_relative_delta", _DEFAULT_CURVATURE_STABILITY_DELTA
        )
    )
    if smoothed_delta > smoothing_limit:
        raise GeometryProfileError(
            f"p95 curvature changes {smoothed_delta:.1%} under 3-point smoothing "
            f"(limit {smoothing_limit:.1%})"
        )

    return GeometryValidation(
        point_count=len(xy),
        segment_count=len(segments),
        orientation=orientation,
        total_distance_m=total_distance,
        seam_distance_m=seam_distance,
        minimum_segment_m=minimum_segment,
        median_segment_m=median_segment,
        maximum_segment_m=maximum_segment,
        minimum_width_m=minimum_width,
        maximum_width_m=maximum_width,
        maximum_curvature_inv_m=maximum_curvature,
        curvature_p95_inv_m=curvature_p95,
        resampled_curvature_p95_inv_m=resampled_p95,
        resampled_curvature_relative_delta=resampled_delta,
        smoothed_curvature_p95_inv_m=smoothed_p95,
        smoothed_curvature_relative_delta=smoothed_delta,
        maximum_smoothing_displacement_m=maximum_smoothing_displacement,
        maximum_smoothing_displacement_fraction=maximum_smoothing_displacement_fraction,
    )


def load_profile(manifest_path: Path, *, asset_root: Path) -> GeometryProfile:
    """Load only after path confinement, raw digest, manifest, and profile quality checks pass."""
    try:
        raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GeometryProfileError(
            f"cannot read geometry manifest {manifest_path}: {error}"
        ) from error
    manifest = _manifest(raw_manifest)

    try:
        root = asset_root.resolve(strict=True)
    except OSError as error:
        raise GeometryProfileError(
            f"geometry root is unavailable: {asset_root}: {error}"
        ) from error
    try:
        asset = (root / Path(manifest.asset_path)).resolve(strict=True)
    except OSError as error:
        raise GeometryProfileError(
            f"geometry asset is unavailable under {root}: {manifest.asset_path}: {error}"
        ) from error
    try:
        asset.relative_to(root)
    except ValueError:
        raise GeometryProfileError(
            "geometry asset path escapes the configured geometry root"
        ) from None
    if not asset.is_file():
        raise GeometryProfileError("geometry asset path is not a regular file")
    try:
        raw = asset.read_bytes()
    except OSError as error:
        raise GeometryProfileError(f"cannot read geometry asset {asset}: {error}") from error
    digest = hashlib.sha256(raw).hexdigest()
    if digest != manifest.sha256:
        raise GeometryProfileError(
            f"geometry SHA-256 mismatch: manifest {manifest.sha256}, actual {digest}"
        )

    x_m, y_m, width_right_m, width_left_m = _parse_csv(raw)
    validation = _validate_geometry(x_m, y_m, width_right_m, width_left_m, manifest.quality)
    x_transformed, y_transformed = _apply_transform(x_m, y_m, manifest.transform)
    return GeometryProfile(
        manifest,
        validation,
        x_transformed,
        y_transformed,
        width_right_m,
        width_left_m,
    )
