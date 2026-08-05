from __future__ import annotations

import argparse
from dataclasses import asdict
import json

from experiments.debug_3gpp_pathloss import build_debug_report
from ran.contracts import Position
from ran.radio.coordinate_calibration import (
    calibration_to_report,
    load_coordinate_calibration,
)
from ran.radio.geometry import (
    analyze_propagation_geometry,
    coordinate_view_from_calibration,
)
from ran.radio.pathloss_3gpp import (
    PathLossApplicabilityError,
    PathLossInputError,
)
from ran.radio.pathloss_3gpp_adapter import (
    GeometryPathLossAdapterError,
    UnsupportedGeometryLinkError,
    path_loss_request_from_geometry,
)
from ran.radio.topology_adapter import load_gnb_site_from_scene
from structure.scene_registry import build_scene


DEFAULT_CASES = (
    ("outdoor_green", Position(420.0, 820.0)),
    ("student_union_center", Position(520.0, 280.0)),
    ("gym_center", Position(860.0, 250.0)),
    ("outdoor_east_of_student_union", Position(700.0, 300.0)),
)


def build_bristol_report(
    *,
    scene_id: str = "bristol_topology",
    gnb_height_m: float,
    ue_height_m: float | None = None,
    allow_extrapolation: bool = False,
) -> dict:
    scene = build_scene(scene_id)
    gnb = load_gnb_site_from_scene(scene)
    calibration = load_coordinate_calibration(scene_id)
    if calibration is None:
        raise ValueError(
            f"No coordinate calibration is configured for scene {scene_id!r}."
        )
    resolved_ue_height_m = (
        calibration.default_ue_height_m
        if ue_height_m is None
        else ue_height_m
    )
    if resolved_ue_height_m is None:
        raise ValueError(
            "UE height must be supplied because calibration has no default."
        )
    coordinate_view = coordinate_view_from_calibration(
        calibration,
        gnb_height_m=gnb_height_m,
        ue_height_m=resolved_ue_height_m,
    )

    case_reports = []
    for case_id, receiver_position in DEFAULT_CASES:
        geometry = analyze_propagation_geometry(
            scene=scene,
            receiver_position=receiver_position,
            gnb=gnb,
            coordinate_view=coordinate_view,
        )
        case_report = {
            "case_id": case_id,
            "geometry": {
                "link_type": geometry.link_type,
                "los_state": geometry.los_state,
                "distance_2d_m": geometry.distance.distance_2d_m,
                "distance_3d_m": geometry.distance.distance_3d_m,
                "outdoor_distance_m": geometry.outdoor_distance_m,
                "indoor_distance_m": geometry.indoor_distance_m,
                "blocking_building_ids": list(geometry.blocking_building_ids),
                "effective_surface_ids": [
                    crossing.surface_id
                    for crossing in geometry.effective_surface_crossings
                ],
            },
        }
        try:
            request = path_loss_request_from_geometry(
                geometry=geometry,
                gnb=gnb,
                bs_height_m=gnb_height_m,
                ut_height_m=resolved_ue_height_m,
            )
            case_report["adaptation"] = {
                "status": "supported",
                "request": asdict(request),
                "path_loss": build_debug_report(
                    request,
                    allow_extrapolation=allow_extrapolation,
                ),
            }
        except UnsupportedGeometryLinkError as exc:
            case_report["adaptation"] = {
                "status": "unsupported",
                "reason": str(exc),
                "path_loss": None,
            }
        except (
            GeometryPathLossAdapterError,
            PathLossApplicabilityError,
            PathLossInputError,
        ) as exc:
            case_report["adaptation"] = {
                "status": "error",
                "reason": str(exc),
                "path_loss": None,
            }
        case_reports.append(case_report)

    return {
        "scene_id": scene_id,
        "gnb": {
            "gnb_id": gnb.gnb_id,
            "carrier_frequency_mhz": gnb.carrier_freq_mhz,
            "height_m": gnb_height_m,
        },
        "ue_height_m": resolved_ue_height_m,
        "calibration": calibration_to_report(calibration),
        "allow_extrapolation": allow_extrapolation,
        "cases": case_reports,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dry-run Bristol Geometry-to-3GPP path-loss adaptation."
    )
    parser.add_argument("--scene", default="bristol_topology")
    parser.add_argument("--gnb-height-m", required=True, type=float)
    parser.add_argument("--ue-height-m", type=float)
    parser.add_argument("--allow-extrapolation", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    try:
        report = build_bristol_report(
            scene_id=args.scene,
            gnb_height_m=args.gnb_height_m,
            ue_height_m=args.ue_height_m,
            allow_extrapolation=args.allow_extrapolation,
        )
    except ValueError as exc:
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
