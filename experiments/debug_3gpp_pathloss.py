from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import math

from ran.radio.pathloss_3gpp import (
    LOS,
    NLOS,
    SCENARIO_INH_OFFICE,
    SCENARIO_UMI_STREET_CANYON,
    STANDARD_REFERENCE,
    PathLossApplicabilityError,
    PathLossInputError,
    PathLossRequest,
    estimate_path_loss_3gpp,
)


def baseline_fspl_db(request: PathLossRequest) -> float:
    """Return the current free-space-form baseline for a physical 3D link."""

    return (
        32.4
        + 20.0 * math.log10(request.carrier_frequency_mhz)
        + 20.0 * math.log10(request.distance_3d_m / 1000.0)
    )


def build_debug_report(
    request: PathLossRequest,
    *,
    allow_extrapolation: bool = False,
) -> dict:
    result = estimate_path_loss_3gpp(
        request,
        allow_extrapolation=allow_extrapolation,
    )
    fspl_db = baseline_fspl_db(request)
    return {
        "input": asdict(request),
        "normalized_units": {
            "carrier_frequency_ghz": request.carrier_frequency_mhz / 1000.0,
            "carrier_frequency_hz": request.carrier_frequency_mhz * 1_000_000.0,
            "distance_2d_m": request.distance_2d_m,
            "distance_3d_m": request.distance_3d_m,
        },
        "standard_reference": STANDARD_REFERENCE,
        "formula_id": result.formula_id,
        "mean_path_loss_db": result.mean_path_loss_db,
        "shadow_fading_std_db": result.shadow_fading_std_db,
        "breakpoint_distance_m": result.breakpoint_distance_m,
        "los_reference_path_loss_db": result.los_reference_path_loss_db,
        "nlos_candidate_path_loss_db": result.nlos_candidate_path_loss_db,
        "baseline_fspl_db": fspl_db,
        "difference_from_baseline_db": result.mean_path_loss_db - fspl_db,
        "is_extrapolated": result.is_extrapolated,
        "warnings": list(result.warnings),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare deterministic 3GPP path loss with the FSPL baseline."
    )
    parser.add_argument(
        "--scenario",
        required=True,
        choices=(SCENARIO_UMI_STREET_CANYON, SCENARIO_INH_OFFICE),
    )
    parser.add_argument(
        "--los-state",
        required=True,
        choices=(LOS, NLOS),
    )
    parser.add_argument("--frequency-mhz", required=True, type=float)
    parser.add_argument("--distance-2d-m", required=True, type=float)
    parser.add_argument("--distance-3d-m", type=float)
    parser.add_argument("--bs-height-m", required=True, type=float)
    parser.add_argument("--ut-height-m", required=True, type=float)
    parser.add_argument("--allow-extrapolation", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    distance_3d_m = args.distance_3d_m
    if distance_3d_m is None:
        distance_3d_m = math.hypot(
            args.distance_2d_m,
            args.bs_height_m - args.ut_height_m,
        )
    request = PathLossRequest(
        scenario=args.scenario,
        los_state=args.los_state,
        carrier_frequency_mhz=args.frequency_mhz,
        distance_2d_m=args.distance_2d_m,
        distance_3d_m=distance_3d_m,
        bs_height_m=args.bs_height_m,
        ut_height_m=args.ut_height_m,
    )
    try:
        report = build_debug_report(
            request,
            allow_extrapolation=args.allow_extrapolation,
        )
    except (PathLossInputError, PathLossApplicabilityError) as exc:
        parser.error(str(exc))

    print(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2 if args.pretty else None,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
