from __future__ import annotations

import argparse
import json

from ran.contracts import Position
from ran.radio.coordinate_calibration import (
    calibration_to_report,
    distance_2d_m,
    distance_3d_m,
    load_coordinate_calibration,
    map_position_to_meters,
)
from ran.radio.topology_adapter import load_gnb_site_from_scene
from structure.scene_registry import build_scene


def main() -> None:
    parser = argparse.ArgumentParser(description="Debug scene coordinate calibration.")
    parser.add_argument("--scene", default="bristol_topology")
    parser.add_argument("--config")
    parser.add_argument("--x", type=float)
    parser.add_argument("--y", type=float)
    parser.add_argument("--gnb-height-m", type=float)
    parser.add_argument("--ue-height-m", type=float)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    calibration = load_coordinate_calibration(args.scene, args.config)
    if calibration is None:
        raise SystemExit(f"No coordinate calibration is configured for scene {args.scene!r}.")

    scene = build_scene(args.scene)
    gnb = load_gnb_site_from_scene(scene)
    if (args.x is None) != (args.y is None):
        raise SystemExit("--x and --y must be supplied together.")
    if args.x is not None and args.y is not None:
        receiver = Position(args.x, args.y)
    elif scene.default_agent_start is not None:
        receiver = Position(*scene.default_agent_start)
    else:
        receiver = Position(0.0, 0.0)

    gnb_height = (
        args.gnb_height_m
        if args.gnb_height_m is not None
        else calibration.gnb_height_m
    )
    ue_height = (
        args.ue_height_m
        if args.ue_height_m is not None
        else calibration.default_ue_height_m
    )
    link_2d_m = distance_2d_m(gnb.position, receiver, calibration)
    link_3d_m = None
    if gnb_height is not None and ue_height is not None:
        link_3d_m = distance_3d_m(
            gnb.position,
            receiver,
            calibration,
            start_height_m=gnb_height,
            end_height_m=ue_height,
        )

    report = calibration_to_report(calibration)
    scene_bounds = scene.rendering.get("map_bounds")
    report["scene_rendering_map_bounds"] = scene_bounds
    report["scene_bounds_match_config"] = (
        scene_bounds is not None
        and tuple(float(value) for value in scene_bounds) == calibration.map_bounds
    )
    report["sample_link"] = {
        "gnb_id": gnb.gnb_id,
        "gnb_map_position": [gnb.position.x, gnb.position.y],
        "gnb_physical_position": _position_report(
            map_position_to_meters(
                gnb.position,
                calibration,
                height_m=gnb_height,
            )
        ),
        "receiver_map_position": [receiver.x, receiver.y],
        "receiver_physical_position": _position_report(
            map_position_to_meters(
                receiver,
                calibration,
                height_m=ue_height,
            )
        ),
        "distance_2d_m": link_2d_m,
        "distance_3d_m": link_3d_m,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2 if args.pretty else None))


def _position_report(position) -> dict:
    return {
        "map_x": position.map_x,
        "map_y": position.map_y,
        "x_m": position.x_m,
        "y_m": position.y_m,
        "height_m": position.height_m,
    }


if __name__ == "__main__":
    main()
