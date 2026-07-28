from __future__ import annotations

from dataclasses import dataclass
import math


STANDARD_REFERENCE = "3GPP TR 38.901 V19.4.0 Table 7.4.1-1"

SCENARIO_UMI_STREET_CANYON = "umi_street_canyon"
SCENARIO_INH_OFFICE = "inh_office"

LOS = "los"
NLOS = "nlos"

FORMULA_UMI_LOS_PL1 = "3gpp_38_901_v19_4_0_umi_los_pl1"
FORMULA_UMI_LOS_PL2 = "3gpp_38_901_v19_4_0_umi_los_pl2"
FORMULA_UMI_NLOS = "3gpp_38_901_v19_4_0_umi_nlos"

SPEED_OF_LIGHT_M_PER_S = 3.0e8
MIN_FREQUENCY_GHZ = 0.5
MAX_FREQUENCY_GHZ = 100.0
UMI_MIN_DISTANCE_2D_M = 10.0
UMI_MAX_DISTANCE_2D_M = 5000.0
UMI_MIN_UT_HEIGHT_M = 1.5
UMI_MAX_UT_HEIGHT_M = 22.5
UMI_REFERENCE_BS_HEIGHT_M = 10.0
UMI_EFFECTIVE_ENVIRONMENT_HEIGHT_M = 1.0
INH_MIN_DISTANCE_3D_M = 1.0
INH_MAX_DISTANCE_3D_M = 150.0
INH_REFERENCE_BS_HEIGHT_M = 3.0
INH_REFERENCE_UT_HEIGHT_M = 1.0


class PathLossInputError(ValueError):
    """Raised when path-loss inputs are mathematically invalid or inconsistent."""


class PathLossApplicabilityError(ValueError):
    """Raised when inputs are outside the selected 3GPP model's stated range."""


@dataclass(frozen=True, slots=True)
class PathLossRequest:
    scenario: str
    los_state: str
    carrier_frequency_mhz: float
    distance_2d_m: float
    distance_3d_m: float
    bs_height_m: float
    ut_height_m: float


@dataclass(frozen=True, slots=True)
class PathLossResult:
    scenario: str
    los_state: str
    mean_path_loss_db: float
    shadow_fading_std_db: float
    formula_id: str
    breakpoint_distance_m: float | None
    los_reference_path_loss_db: float | None
    nlos_candidate_path_loss_db: float | None
    is_extrapolated: bool
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _ValidatedRequest:
    frequency_ghz: float
    frequency_hz: float
    is_extrapolated: bool
    warnings: tuple[str, ...]


def estimate_path_loss_3gpp(
    request: PathLossRequest,
    *,
    allow_extrapolation: bool = False,
) -> PathLossResult:
    """Return deterministic 3GPP mean path loss and model metadata."""
    validated = _validate_request(
        request,
        allow_extrapolation=allow_extrapolation,
    )
    if request.scenario == SCENARIO_UMI_STREET_CANYON:
        return _estimate_umi_street_canyon(request, validated)
    raise NotImplementedError("InH Office path loss is implemented in Stage 1C.")


def _validate_request(
    request: PathLossRequest,
    *,
    allow_extrapolation: bool = False,
) -> _ValidatedRequest:
    if request.scenario not in {
        SCENARIO_UMI_STREET_CANYON,
        SCENARIO_INH_OFFICE,
    }:
        raise PathLossInputError(f"Unsupported 3GPP scenario: {request.scenario!r}.")
    if request.los_state not in {LOS, NLOS}:
        raise PathLossInputError(f"Unsupported LOS state: {request.los_state!r}.")

    numeric_fields = (
        ("carrier_frequency_mhz", request.carrier_frequency_mhz),
        ("distance_2d_m", request.distance_2d_m),
        ("distance_3d_m", request.distance_3d_m),
        ("bs_height_m", request.bs_height_m),
        ("ut_height_m", request.ut_height_m),
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

    if request.carrier_frequency_mhz <= 0.0:
        raise PathLossInputError("carrier_frequency_mhz must be greater than zero.")
    if request.distance_2d_m < 0.0:
        raise PathLossInputError("distance_2d_m must not be negative.")
    if request.distance_3d_m <= 0.0:
        raise PathLossInputError("distance_3d_m must be greater than zero.")
    if request.distance_3d_m < request.distance_2d_m:
        raise PathLossInputError("distance_3d_m must not be less than distance_2d_m.")
    if request.bs_height_m <= 0.0 or request.ut_height_m <= 0.0:
        raise PathLossInputError("BS and UT heights must be greater than zero.")

    expected_distance_3d_m = math.hypot(
        request.distance_2d_m,
        request.bs_height_m - request.ut_height_m,
    )
    distance_tolerance_m = max(0.05, expected_distance_3d_m * 1e-4)
    if abs(request.distance_3d_m - expected_distance_3d_m) > distance_tolerance_m:
        raise PathLossInputError(
            "distance_3d_m is inconsistent with distance_2d_m and antenna heights."
        )

    frequency_ghz = request.carrier_frequency_mhz / 1000.0
    frequency_hz = request.carrier_frequency_mhz * 1_000_000.0
    applicability_issues: list[str] = []
    warnings: list[str] = []

    if not MIN_FREQUENCY_GHZ < frequency_ghz < MAX_FREQUENCY_GHZ:
        applicability_issues.append(
            "frequency_outside_3gpp_range: expected 0.5 < fc_GHz < 100"
        )

    if request.scenario == SCENARIO_UMI_STREET_CANYON:
        if (
            request.bs_height_m <= UMI_EFFECTIVE_ENVIRONMENT_HEIGHT_M
            or request.ut_height_m <= UMI_EFFECTIVE_ENVIRONMENT_HEIGHT_M
        ):
            raise PathLossInputError(
                "UMi effective BS and UT heights must be greater than zero."
            )
        if not (
            UMI_MIN_DISTANCE_2D_M
            <= request.distance_2d_m
            <= UMI_MAX_DISTANCE_2D_M
        ):
            applicability_issues.append(
                "umi_distance_outside_applicability: expected 10 <= d2D <= 5000 m"
            )
        if not (
            UMI_MIN_UT_HEIGHT_M
            <= request.ut_height_m
            <= UMI_MAX_UT_HEIGHT_M
        ):
            applicability_issues.append(
                "umi_ut_height_outside_applicability: "
                "expected 1.5 <= hUT <= 22.5 m"
            )
        if not math.isclose(
            request.bs_height_m,
            UMI_REFERENCE_BS_HEIGHT_M,
            abs_tol=1e-9,
        ):
            warnings.append("non_reference_height: UMi reference hBS is 10 m")
    else:
        if not (
            INH_MIN_DISTANCE_3D_M
            <= request.distance_3d_m
            <= INH_MAX_DISTANCE_3D_M
        ):
            applicability_issues.append(
                "inh_distance_outside_applicability: expected 1 <= d3D <= 150 m"
            )
        if not (
            math.isclose(
                request.bs_height_m,
                INH_REFERENCE_BS_HEIGHT_M,
                abs_tol=1e-9,
            )
            and math.isclose(
                request.ut_height_m,
                INH_REFERENCE_UT_HEIGHT_M,
                abs_tol=1e-9,
            )
        ):
            warnings.append(
                "non_reference_height: InH reference hBS=3 m and hUT=1 m"
            )

    if applicability_issues and not allow_extrapolation:
        raise PathLossApplicabilityError("; ".join(applicability_issues))
    if applicability_issues:
        warnings.extend(applicability_issues)

    return _ValidatedRequest(
        frequency_ghz=frequency_ghz,
        frequency_hz=frequency_hz,
        is_extrapolated=bool(applicability_issues),
        warnings=tuple(warnings),
    )


def _estimate_umi_street_canyon(
    request: PathLossRequest,
    validated: _ValidatedRequest,
) -> PathLossResult:
    breakpoint_distance_m = _umi_breakpoint_distance_m(request, validated)
    los_path_loss_db, los_formula_id = _umi_los_path_loss_db(
        request,
        validated,
        breakpoint_distance_m,
    )

    if request.los_state == LOS:
        return PathLossResult(
            scenario=request.scenario,
            los_state=request.los_state,
            mean_path_loss_db=los_path_loss_db,
            shadow_fading_std_db=4.0,
            formula_id=los_formula_id,
            breakpoint_distance_m=breakpoint_distance_m,
            los_reference_path_loss_db=los_path_loss_db,
            nlos_candidate_path_loss_db=None,
            is_extrapolated=validated.is_extrapolated,
            warnings=validated.warnings,
        )

    nlos_candidate_db = (
        35.3 * math.log10(request.distance_3d_m)
        + 22.4
        + 21.3 * math.log10(validated.frequency_ghz)
        - 0.3 * (request.ut_height_m - 1.5)
    )
    return PathLossResult(
        scenario=request.scenario,
        los_state=request.los_state,
        mean_path_loss_db=max(los_path_loss_db, nlos_candidate_db),
        shadow_fading_std_db=7.82,
        formula_id=FORMULA_UMI_NLOS,
        breakpoint_distance_m=breakpoint_distance_m,
        los_reference_path_loss_db=los_path_loss_db,
        nlos_candidate_path_loss_db=nlos_candidate_db,
        is_extrapolated=validated.is_extrapolated,
        warnings=validated.warnings,
    )


def _umi_breakpoint_distance_m(
    request: PathLossRequest,
    validated: _ValidatedRequest,
) -> float:
    effective_bs_height_m = (
        request.bs_height_m - UMI_EFFECTIVE_ENVIRONMENT_HEIGHT_M
    )
    effective_ut_height_m = (
        request.ut_height_m - UMI_EFFECTIVE_ENVIRONMENT_HEIGHT_M
    )
    return (
        4.0
        * effective_bs_height_m
        * effective_ut_height_m
        * validated.frequency_hz
        / SPEED_OF_LIGHT_M_PER_S
    )


def _umi_los_path_loss_db(
    request: PathLossRequest,
    validated: _ValidatedRequest,
    breakpoint_distance_m: float,
) -> tuple[float, str]:
    if request.distance_2d_m <= breakpoint_distance_m:
        path_loss_db = (
            32.4
            + 21.0 * math.log10(request.distance_3d_m)
            + 20.0 * math.log10(validated.frequency_ghz)
        )
        return path_loss_db, FORMULA_UMI_LOS_PL1

    height_difference_m = request.bs_height_m - request.ut_height_m
    path_loss_db = (
        32.4
        + 40.0 * math.log10(request.distance_3d_m)
        + 20.0 * math.log10(validated.frequency_ghz)
        - 9.5
        * math.log10(
            breakpoint_distance_m**2 + height_difference_m**2
        )
    )
    return path_loss_db, FORMULA_UMI_LOS_PL2
