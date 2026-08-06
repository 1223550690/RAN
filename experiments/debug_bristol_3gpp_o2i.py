from __future__ import annotations

import argparse
from dataclasses import asdict
import json

from ran.contracts import Position
from ran.radio.coordinate_calibration import (
    calibration_to_report,
    load_coordinate_calibration,
)
from ran.radio.geometry import (
    analyze_propagation_geometry,
    coordinate_view_from_calibration,
)
from ran.radio.pathloss_3gpp_adapter import (
    GeometryPathLossAdapterError,
    o2i_path_loss_request_from_geometry,
)
from ran.radio.pathloss_3gpp_o2i import (
    HIGH_LOSS,
    LOW_LOSS,
    STANDARD_REFERENCE,
    estimate_o2i_path_loss_3gpp,
)
from ran.radio.topology_adapter import load_gnb_site_from_scene
from structure.scene_registry import build_scene


DEFAULT_O2I_CASES = (
    ("student_union_center", Position(520.0, 280.0)),
    ("gym_center", Position(860.0, 250.0)),
)


def build_bristol_o2i_report(
    *,
    scene_id: str = "bristol_topology",
    gnb_height_m: float,
    ue_height_m: float | None = None,
    penetration_model: str = LOW_LOSS,
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

    cases = []
    for case_id, receiver_position in DEFAULT_O2I_CASES:
        geometry = analyze_propagation_geometry(
            scene=scene,
            receiver_position=receiver_position,
            gnb=gnb,
            coordinate_view=coordinate_view,
        )
        raw_wall_loss_db = sum(
            crossing.penetration_loss_db
            for crossing in geometry.effective_surface_crossings
        )
        case = {
            "case_id": case_id,
            "geometry": {
                "link_type": geometry.link_type,
                "geometry_los_state": geometry.los_state,
                "distance_2d_m": geometry.distance.distance_2d_m,
                "distance_3d_m": geometry.distance.distance_3d_m,
                "outdoor_distance_m": geometry.outdoor_distance_m,
                "indoor_distance_m": geometry.indoor_distance_m,
                "blocking_building_ids": list(geometry.blocking_building_ids),
                "target_exterior_surface_ids": [
                    crossing.surface_id
                    for crossing in geometry.exterior_surfaces_crossed
                ],
            },
            "double_counting_guard": {
                "raw_map_penetration_loss_db": raw_wall_loss_db,
                "used_in_3gpp_o2i_total": False,
            },
        }
        try:
            request = o2i_path_loss_request_from_geometry(
                geometry=geometry,
                gnb=gnb,
                bs_height_m=gnb_height_m,
                ut_height_m=resolved_ue_height_m,
                penetration_model=penetration_model,
            )
            result = estimate_o2i_path_loss_3gpp(
                request,
                allow_extrapolation=allow_extrapolation,
            )
            case["adaptation"] = {
                "status": "supported",
                "outdoor_los_rule": (
                    "nlos_if_blocking_building_ids_else_los"
                ),
                "request": asdict(request),
                "result": asdict(result),
            }
        except (GeometryPathLossAdapterError, ValueError) as exc:
            case["adaptation"] = {
                "status": "error",
                "reason": str(exc),
                "result": None,
            }
        cases.append(case)

    return {
        "stage": "4B",
        "scene_id": scene_id,
        "standard_reference": STANDARD_REFERENCE,
        "penetration_model": penetration_model,
        "random_policy": "zero_realization_with_std_metadata",
        "indoor_depth_policy": "geometry_measured",
        "runtime_integration": False,
        "calibration": calibration_to_report(calibration),
        "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Report decomposed Stage 4B O2I path loss for Bristol."
    )
    parser.add_argument("--scene", default="bristol_topology")
    parser.add_argument("--gnb-height-m", required=True, type=float)
    parser.add_argument("--ue-height-m", type=float)
    parser.add_argument(
        "--penetration-model",
        choices=(LOW_LOSS, HIGH_LOSS),
        default=LOW_LOSS,
    )
    parser.add_argument("--allow-extrapolation", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    report = build_bristol_o2i_report(
        scene_id=args.scene,
        gnb_height_m=args.gnb_height_m,
        ue_height_m=args.ue_height_m,
        penetration_model=args.penetration_model,
        allow_extrapolation=args.allow_extrapolation,
    )
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
