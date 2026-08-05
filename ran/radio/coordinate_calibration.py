from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path

from ran.contracts import Position


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CALIBRATION_CONFIG_PATH = PROJECT_ROOT / "configs" / "ran" / "coordinate_calibration.json"
SUPPORTED_SCHEMA_VERSION = "1"
SUPPORTED_STATUSES = {"provisional", "confirmed"}
SUPPORTED_Y_AXIS_DIRECTIONS = {"down", "up"}
CONFIRMED_MAX_RELATIVE_ERROR = 0.10
UNIFORM_SCALE_REL_TOLERANCE = 1e-9


class CalibrationConfigError(ValueError):
    """Raised when coordinate calibration data is invalid or inconsistent."""


@dataclass(frozen=True, slots=True)
class CalibrationAnchor:
    anchor_id: str
    map_start: tuple[float, float]
    map_end: tuple[float, float]
    known_distance_m: float
    source: str
    uncertainty_m: float | None = None


@dataclass(frozen=True, slots=True)
class CalibrationDefinition:
    scene_id: str
    calibration_id: str
    status: str
    source: str
    map_bounds: tuple[float, float, float, float]
    physical_width_m: float
    physical_height_m: float
    origin_map: tuple[float, float]
    y_axis_direction: str
    gnb_height_m: float | None
    default_ue_height_m: float | None
    anchors: tuple[CalibrationAnchor, ...] = ()


@dataclass(frozen=True, slots=True)
class CalibrationAnchorResidual:
    anchor_id: str
    known_distance_m: float
    predicted_distance_m: float
    error_m: float
    relative_error: float
    source: str


@dataclass(frozen=True, slots=True)
class CoordinateCalibrationResult:
    scene_id: str
    calibration_id: str
    status: str
    source: str
    map_bounds: tuple[float, float, float, float]
    physical_width_m: float
    physical_height_m: float
    meters_per_map_unit_x: float
    meters_per_map_unit_y: float
    meters_per_map_unit: float | None
    origin_map: tuple[float, float]
    y_axis_direction: str
    gnb_height_m: float | None
    default_ue_height_m: float | None
    anchor_residuals: tuple[CalibrationAnchorResidual, ...]
    max_relative_error: float | None
    rms_error_m: float | None
    source_summary: tuple[str, ...]

    @property
    def anchor_count(self) -> int:
        return len(self.anchor_residuals)


@dataclass(frozen=True, slots=True)
class PhysicalPosition:
    map_x: float
    map_y: float
    x_m: float
    y_m: float
    height_m: float | None = None


def load_calibration_definition(
    scene_id: str,
    config_path: str | Path | None = None,
) -> CalibrationDefinition | None:
    """Load one scene calibration without applying it to the runtime."""

    path = Path(config_path) if config_path is not None else DEFAULT_CALIBRATION_CONFIG_PATH
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CalibrationConfigError(f"Calibration config not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CalibrationConfigError(f"Invalid calibration JSON in {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise CalibrationConfigError("Calibration config root must be an object.")
    schema_version = str(raw.get("schema_version", ""))
    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise CalibrationConfigError(
            f"Unsupported calibration schema_version {schema_version!r}; "
            f"expected {SUPPORTED_SCHEMA_VERSION!r}."
        )
    scenes = raw.get("scenes")
    if not isinstance(scenes, dict):
        raise CalibrationConfigError("Calibration config 'scenes' must be an object.")
    scene_data = scenes.get(scene_id)
    if scene_data is None:
        return None
    if not isinstance(scene_data, dict):
        raise CalibrationConfigError(f"Calibration for scene {scene_id!r} must be an object.")
    return _parse_definition(scene_id, scene_data)


def load_coordinate_calibration(
    scene_id: str,
    config_path: str | Path | None = None,
) -> CoordinateCalibrationResult | None:
    """Load and resolve one scene calibration, returning None for unknown scenes."""

    definition = load_calibration_definition(scene_id, config_path)
    if definition is None:
        return None
    return resolve_coordinate_calibration(definition)


def resolve_coordinate_calibration(
    definition: CalibrationDefinition,
) -> CoordinateCalibrationResult:
    """Derive x/y map scales and validate any reference anchors."""

    if definition.status not in SUPPORTED_STATUSES:
        raise CalibrationConfigError(
            f"Unsupported calibration status {definition.status!r}; "
            f"expected one of {sorted(SUPPORTED_STATUSES)}."
        )
    if definition.y_axis_direction not in SUPPORTED_Y_AXIS_DIRECTIONS:
        raise CalibrationConfigError(
            f"Unsupported y_axis_direction {definition.y_axis_direction!r}; "
            f"expected one of {sorted(SUPPORTED_Y_AXIS_DIRECTIONS)}."
        )
    map_bounds = _bounds(definition.map_bounds, "map_bounds")
    origin_map = _point(definition.origin_map, "origin_map")
    physical_width_m = _positive_number(
        definition.physical_width_m,
        "physical_width_m",
    )
    physical_height_m = _positive_number(
        definition.physical_height_m,
        "physical_height_m",
    )
    min_x, min_y, max_x, max_y = map_bounds
    map_width = max_x - min_x
    map_height = max_y - min_y
    _require_positive_finite(map_width, "map width")
    _require_positive_finite(map_height, "map height")

    scale_x = physical_width_m / map_width
    scale_y = physical_height_m / map_height
    uniform_scale = None
    if math.isclose(
        scale_x,
        scale_y,
        rel_tol=UNIFORM_SCALE_REL_TOLERANCE,
        abs_tol=0.0,
    ):
        uniform_scale = (scale_x + scale_y) / 2.0

    residuals = tuple(
        _anchor_residual(anchor, scale_x=scale_x, scale_y=scale_y)
        for anchor in definition.anchors
    )
    max_relative_error = (
        max(residual.relative_error for residual in residuals)
        if residuals
        else None
    )
    rms_error_m = (
        math.sqrt(sum(residual.error_m**2 for residual in residuals) / len(residuals))
        if residuals
        else None
    )

    if definition.status == "confirmed":
        if len(residuals) < 2:
            raise CalibrationConfigError(
                "Confirmed calibration requires at least two reference anchors."
            )
        if (
            max_relative_error is not None
            and max_relative_error > CONFIRMED_MAX_RELATIVE_ERROR
        ):
            raise CalibrationConfigError(
                "Confirmed calibration exceeds the maximum anchor relative error: "
                f"{max_relative_error:.2%} > {CONFIRMED_MAX_RELATIVE_ERROR:.2%}."
            )

    sources = _unique_strings(
        [definition.source, *(anchor.source for anchor in definition.anchors)]
    )
    return CoordinateCalibrationResult(
        scene_id=definition.scene_id,
        calibration_id=definition.calibration_id,
        status=definition.status,
        source=definition.source,
        map_bounds=map_bounds,
        physical_width_m=physical_width_m,
        physical_height_m=physical_height_m,
        meters_per_map_unit_x=scale_x,
        meters_per_map_unit_y=scale_y,
        meters_per_map_unit=uniform_scale,
        origin_map=origin_map,
        y_axis_direction=definition.y_axis_direction,
        gnb_height_m=definition.gnb_height_m,
        default_ue_height_m=definition.default_ue_height_m,
        anchor_residuals=residuals,
        max_relative_error=max_relative_error,
        rms_error_m=rms_error_m,
        source_summary=sources,
    )


def map_position_to_meters(
    position: Position,
    calibration: CoordinateCalibrationResult,
    *,
    height_m: float | None = None,
) -> PhysicalPosition:
    """Convert a map point to local physical coordinates."""

    map_x = _finite_number(position.x, "position.x")
    map_y = _finite_number(position.y, "position.y")
    if height_m is not None:
        height_m = _nonnegative_number(height_m, "height_m")

    x_m = (map_x - calibration.origin_map[0]) * calibration.meters_per_map_unit_x
    y_m = (map_y - calibration.origin_map[1]) * calibration.meters_per_map_unit_y
    if calibration.y_axis_direction == "up":
        y_m = -y_m
    return PhysicalPosition(
        map_x=map_x,
        map_y=map_y,
        x_m=x_m,
        y_m=y_m,
        height_m=height_m,
    )


def distance_2d_m(
    start: Position,
    end: Position,
    calibration: CoordinateCalibrationResult,
) -> float:
    """Return horizontal physical distance after x/y calibration."""

    dx_m = (
        _finite_number(end.x, "end.x") - _finite_number(start.x, "start.x")
    ) * calibration.meters_per_map_unit_x
    dy_m = (
        _finite_number(end.y, "end.y") - _finite_number(start.y, "start.y")
    ) * calibration.meters_per_map_unit_y
    return math.hypot(dx_m, dy_m)


def distance_3d_m(
    start: Position,
    end: Position,
    calibration: CoordinateCalibrationResult,
    *,
    start_height_m: float,
    end_height_m: float,
) -> float:
    """Return 2.5D/3D link distance using explicit endpoint heights."""

    start_height = _nonnegative_number(start_height_m, "start_height_m")
    end_height = _nonnegative_number(end_height_m, "end_height_m")
    horizontal_distance = distance_2d_m(start, end, calibration)
    return math.hypot(horizontal_distance, start_height - end_height)


def calibration_to_report(calibration: CoordinateCalibrationResult) -> dict:
    """Create a JSON-serializable debug report."""

    warnings = []
    if calibration.status == "provisional" and calibration.anchor_count == 0:
        warnings.append("provisional_calibration_has_no_reference_anchors")
    if (
        calibration.status == "provisional"
        and calibration.max_relative_error is not None
        and calibration.max_relative_error > CONFIRMED_MAX_RELATIVE_ERROR
    ):
        warnings.append("provisional_anchor_error_exceeds_confirmed_threshold")

    return {
        "scene_id": calibration.scene_id,
        "calibration_id": calibration.calibration_id,
        "status": calibration.status,
        "source": calibration.source,
        "map_bounds": list(calibration.map_bounds),
        "physical_extent_m": {
            "width": calibration.physical_width_m,
            "height": calibration.physical_height_m,
        },
        "meters_per_map_unit_x": calibration.meters_per_map_unit_x,
        "meters_per_map_unit_y": calibration.meters_per_map_unit_y,
        "meters_per_map_unit": calibration.meters_per_map_unit,
        "origin_map": list(calibration.origin_map),
        "y_axis_direction": calibration.y_axis_direction,
        "gnb_height_m": calibration.gnb_height_m,
        "default_ue_height_m": calibration.default_ue_height_m,
        "anchor_count": calibration.anchor_count,
        "anchor_residuals": [
            {
                "anchor_id": residual.anchor_id,
                "known_distance_m": residual.known_distance_m,
                "predicted_distance_m": residual.predicted_distance_m,
                "error_m": residual.error_m,
                "relative_error": residual.relative_error,
                "source": residual.source,
            }
            for residual in calibration.anchor_residuals
        ],
        "max_relative_error": calibration.max_relative_error,
        "rms_error_m": calibration.rms_error_m,
        "source_summary": list(calibration.source_summary),
        "validation_warnings": warnings,
    }


def _parse_definition(scene_id: str, data: dict) -> CalibrationDefinition:
    calibration_id = _required_string(data, "calibration_id")
    status = _required_string(data, "status")
    if status not in SUPPORTED_STATUSES:
        raise CalibrationConfigError(
            f"Unsupported calibration status {status!r}; "
            f"expected one of {sorted(SUPPORTED_STATUSES)}."
        )
    source = _required_string(data, "source")
    map_bounds = _bounds(data.get("map_bounds"), "map_bounds")

    extent = data.get("physical_extent_m")
    if not isinstance(extent, dict):
        raise CalibrationConfigError("'physical_extent_m' must be an object.")
    physical_width_m = _positive_number(extent.get("width"), "physical_extent_m.width")
    physical_height_m = _positive_number(
        extent.get("height"),
        "physical_extent_m.height",
    )

    origin_map = _point(data.get("origin_map"), "origin_map")
    y_axis_direction = _required_string(data, "y_axis_direction")
    if y_axis_direction not in SUPPORTED_Y_AXIS_DIRECTIONS:
        raise CalibrationConfigError(
            f"Unsupported y_axis_direction {y_axis_direction!r}; "
            f"expected one of {sorted(SUPPORTED_Y_AXIS_DIRECTIONS)}."
        )

    anchors_data = data.get("anchors", [])
    if not isinstance(anchors_data, list):
        raise CalibrationConfigError("'anchors' must be an array.")
    anchors = tuple(
        _parse_anchor(anchor_data, index)
        for index, anchor_data in enumerate(anchors_data)
    )
    return CalibrationDefinition(
        scene_id=scene_id,
        calibration_id=calibration_id,
        status=status,
        source=source,
        map_bounds=map_bounds,
        physical_width_m=physical_width_m,
        physical_height_m=physical_height_m,
        origin_map=origin_map,
        y_axis_direction=y_axis_direction,
        gnb_height_m=_optional_nonnegative_number(data.get("gnb_height_m"), "gnb_height_m"),
        default_ue_height_m=_optional_nonnegative_number(
            data.get("default_ue_height_m"),
            "default_ue_height_m",
        ),
        anchors=anchors,
    )


def _parse_anchor(data: object, index: int) -> CalibrationAnchor:
    if not isinstance(data, dict):
        raise CalibrationConfigError(f"anchors[{index}] must be an object.")
    uncertainty = data.get("uncertainty_m")
    return CalibrationAnchor(
        anchor_id=_required_string(data, "anchor_id", prefix=f"anchors[{index}]."),
        map_start=_point(data.get("map_start"), f"anchors[{index}].map_start"),
        map_end=_point(data.get("map_end"), f"anchors[{index}].map_end"),
        known_distance_m=_positive_number(
            data.get("known_distance_m"),
            f"anchors[{index}].known_distance_m",
        ),
        source=_required_string(data, "source", prefix=f"anchors[{index}]."),
        uncertainty_m=(
            _positive_number(uncertainty, f"anchors[{index}].uncertainty_m")
            if uncertainty is not None
            else None
        ),
    )


def _anchor_residual(
    anchor: CalibrationAnchor,
    *,
    scale_x: float,
    scale_y: float,
) -> CalibrationAnchorResidual:
    map_start = _point(anchor.map_start, f"anchor {anchor.anchor_id!r}.map_start")
    map_end = _point(anchor.map_end, f"anchor {anchor.anchor_id!r}.map_end")
    known_distance_m = _positive_number(
        anchor.known_distance_m,
        f"anchor {anchor.anchor_id!r}.known_distance_m",
    )
    if anchor.uncertainty_m is not None:
        _positive_number(
            anchor.uncertainty_m,
            f"anchor {anchor.anchor_id!r}.uncertainty_m",
        )
    dx_map = map_end[0] - map_start[0]
    dy_map = map_end[1] - map_start[1]
    if dx_map == 0.0 and dy_map == 0.0:
        raise CalibrationConfigError(
            f"Calibration anchor {anchor.anchor_id!r} has identical map points."
        )
    predicted = math.hypot(dx_map * scale_x, dy_map * scale_y)
    error = predicted - known_distance_m
    return CalibrationAnchorResidual(
        anchor_id=anchor.anchor_id,
        known_distance_m=known_distance_m,
        predicted_distance_m=predicted,
        error_m=error,
        relative_error=abs(error) / known_distance_m,
        source=anchor.source,
    )


def _required_string(data: dict, key: str, *, prefix: str = "") -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CalibrationConfigError(f"{prefix}{key} must be a non-empty string.")
    return value.strip()


def _bounds(value: object, name: str) -> tuple[float, float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise CalibrationConfigError(f"{name} must contain four numbers.")
    bounds = tuple(_finite_number(item, f"{name}[{index}]") for index, item in enumerate(value))
    if bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
        raise CalibrationConfigError(f"{name} must have positive width and height.")
    return bounds


def _point(value: object, name: str) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise CalibrationConfigError(f"{name} must contain two numbers.")
    return (
        _finite_number(value[0], f"{name}[0]"),
        _finite_number(value[1], f"{name}[1]"),
    )


def _finite_number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CalibrationConfigError(f"{name} must be a number.")
    number = float(value)
    if not math.isfinite(number):
        raise CalibrationConfigError(f"{name} must be finite.")
    return number


def _positive_number(value: object, name: str) -> float:
    number = _finite_number(value, name)
    _require_positive_finite(number, name)
    return number


def _nonnegative_number(value: object, name: str) -> float:
    number = _finite_number(value, name)
    if number < 0.0:
        raise CalibrationConfigError(f"{name} must be non-negative.")
    return number


def _optional_nonnegative_number(value: object, name: str) -> float | None:
    if value is None:
        return None
    return _nonnegative_number(value, name)


def _require_positive_finite(value: float, name: str) -> None:
    if not math.isfinite(value) or value <= 0.0:
        raise CalibrationConfigError(f"{name} must be positive and finite.")


def _unique_strings(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))
