from __future__ import annotations

from dataclasses import dataclass
import math

from ran.radio.pathloss_3gpp import (
    PathLossApplicabilityError,
    PathLossInputError,
    PathLossRequest,
    PathLossResult,
    SCENARIO_UMI_STREET_CANYON,
    estimate_path_loss_3gpp,
)


STANDARD_REFERENCE = "3GPP TR 38.901 V19.4.0 Clause 7.4.3.1"

LOW_LOSS = "low_loss"
HIGH_LOSS = "high_loss"

FORMULA_O2I_LOW_LOSS = "3gpp_38_901_v19_4_0_o2i_low_loss"
FORMULA_O2I_HIGH_LOSS = "3gpp_38_901_v19_4_0_o2i_high_loss"

MAX_STANDARD_UMI_INDOOR_DEPTH_M = 25.0
NON_PERPENDICULAR_INCIDENCE_LOSS_DB = 5.0


@dataclass(frozen=True, slots=True)
class O2IPathLossRequest:
    basic_outdoor_request: PathLossRequest
    indoor_distance_m: float
    penetration_model: str
    penetration_residual_db: float = 0.0
    indoor_distance_source: str = "provided"
    include_external_wall_loss: bool = True
    include_indoor_loss: bool = True


@dataclass(frozen=True, slots=True)
class MaterialLossComponent:
    material: str
    proportion: float
    penetration_loss_db: float
    weighted_linear_power: float


@dataclass(frozen=True, slots=True)
class O2IPathLossResult:
    penetration_model: str
    formula_id: str
    basic_outdoor_path_loss: PathLossResult
    basic_outdoor_path_loss_db: float
    external_wall_loss_db: float
    indoor_loss_db: float
    penetration_residual_db: float
    mean_path_loss_db: float
    total_path_loss_db: float
    penetration_loss_std_db: float
    indoor_distance_m: float
    indoor_distance_source: str
    material_components: tuple[MaterialLossComponent, ...]
    is_extrapolated: bool
    warnings: tuple[str, ...]


def estimate_o2i_path_loss_3gpp(
    request: O2IPathLossRequest,
    *,
    allow_extrapolation: bool = False,
) -> O2IPathLossResult:
    """Return decomposed 3GPP O2I building-penetration path loss."""

    warnings, depth_is_extrapolated = _validate_request(
        request,
        allow_extrapolation=allow_extrapolation,
    )
    basic_result = estimate_path_loss_3gpp(
        request.basic_outdoor_request,
        allow_extrapolation=allow_extrapolation,
    )
    frequency_ghz = request.basic_outdoor_request.carrier_frequency_mhz / 1000.0
    materials, penetration_std_db, formula_id = _profile_components(
        request.penetration_model,
        frequency_ghz,
    )
    external_wall_loss_db = (
        NON_PERPENDICULAR_INCIDENCE_LOSS_DB
        - 10.0
        * math.log10(sum(item.weighted_linear_power for item in materials))
        if request.include_external_wall_loss
        else 0.0
    )
    indoor_loss_db = (
        0.5 * request.indoor_distance_m
        if request.include_indoor_loss
        else 0.0
    )
    mean_path_loss_db = (
        basic_result.mean_path_loss_db
        + external_wall_loss_db
        + indoor_loss_db
    )

    combined_warnings = list(basic_result.warnings)
    combined_warnings.extend(warnings)
    if not request.include_external_wall_loss:
        combined_warnings.append("external_wall_loss_disabled_for_comparison")
    if not request.include_indoor_loss:
        combined_warnings.append("indoor_loss_disabled_for_comparison")

    return O2IPathLossResult(
        penetration_model=request.penetration_model,
        formula_id=formula_id,
        basic_outdoor_path_loss=basic_result,
        basic_outdoor_path_loss_db=basic_result.mean_path_loss_db,
        external_wall_loss_db=external_wall_loss_db,
        indoor_loss_db=indoor_loss_db,
        penetration_residual_db=request.penetration_residual_db,
        mean_path_loss_db=mean_path_loss_db,
        total_path_loss_db=mean_path_loss_db + request.penetration_residual_db,
        penetration_loss_std_db=penetration_std_db,
        indoor_distance_m=request.indoor_distance_m,
        indoor_distance_source=request.indoor_distance_source,
        material_components=materials,
        is_extrapolated=basic_result.is_extrapolated or depth_is_extrapolated,
        warnings=tuple(combined_warnings),
    )


def _validate_request(
    request: O2IPathLossRequest,
    *,
    allow_extrapolation: bool,
) -> tuple[list[str], bool]:
    if request.basic_outdoor_request.scenario != SCENARIO_UMI_STREET_CANYON:
        raise PathLossInputError(
            "O2I basic_outdoor_request must use UMi Street Canyon."
        )
    if request.penetration_model not in {LOW_LOSS, HIGH_LOSS}:
        raise PathLossInputError(
            f"Unsupported O2I penetration model: {request.penetration_model!r}."
        )
    if not request.indoor_distance_source:
        raise PathLossInputError("indoor_distance_source must not be empty.")

    numeric_fields = (
        ("indoor_distance_m", request.indoor_distance_m),
        ("penetration_residual_db", request.penetration_residual_db),
    )
    for field_name, value in numeric_fields:
        try:
            is_finite = math.isfinite(value)
        except TypeError as exc:
            raise PathLossInputError(
                f"{field_name} must be a finite number."
            ) from exc
        if not is_finite:
            raise PathLossInputError(f"{field_name} must be finite.")
    if request.indoor_distance_m < 0.0:
        raise PathLossInputError("indoor_distance_m must not be negative.")

    depth_is_extrapolated = (
        request.indoor_distance_m > MAX_STANDARD_UMI_INDOOR_DEPTH_M
    )
    if depth_is_extrapolated and not allow_extrapolation:
        raise PathLossApplicabilityError(
            "indoor_distance_m exceeds the 25 m support of the standard UMi "
            "O2I indoor-depth generation; pass allow_extrapolation=True for "
            "map-measured depth."
        )

    warnings: list[str] = []
    if request.indoor_distance_source == "geometry_measured":
        warnings.append(
            "map_aware_deviation: indoor depth comes from Geometry instead of "
            "3GPP UT-specific random generation"
        )
    if depth_is_extrapolated:
        warnings.append(
            "o2i_indoor_depth_outside_standard_support: expected d2D-in <= 25 m"
        )
    if request.penetration_residual_db == 0.0:
        warnings.append(
            "deterministic_penetration_mean: random penetration realization is zero"
        )
    return warnings, depth_is_extrapolated


def _profile_components(
    penetration_model: str,
    frequency_ghz: float,
) -> tuple[tuple[MaterialLossComponent, ...], float, str]:
    concrete_loss_db = 5.0 + 4.0 * frequency_ghz
    if penetration_model == LOW_LOSS:
        definitions = (
            ("standard_multi_pane_glass", 0.3, 2.0 + 0.2 * frequency_ghz),
            ("concrete", 0.7, concrete_loss_db),
        )
        penetration_std_db = 4.4
        formula_id = FORMULA_O2I_LOW_LOSS
    else:
        definitions = (
            ("irr_glass", 0.7, 25.4 + 0.11 * frequency_ghz),
            ("concrete", 0.3, concrete_loss_db),
        )
        penetration_std_db = 6.5
        formula_id = FORMULA_O2I_HIGH_LOSS

    components = tuple(
        MaterialLossComponent(
            material=material,
            proportion=proportion,
            penetration_loss_db=loss_db,
            weighted_linear_power=proportion * 10.0 ** (-loss_db / 10.0),
        )
        for material, proportion, loss_db in definitions
    )
    return components, penetration_std_db, formula_id
