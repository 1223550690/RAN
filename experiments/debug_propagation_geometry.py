from __future__ import annotations

import argparse
import json

from ran.contracts import Position
from ran.radio.coordinate_calibration import load_coordinate_calibration
from ran.radio.geometry import (
    analyze_propagation_geometry,
    coordinate_view_from_calibration,
    geometry_to_report,
)
from ran.radio.topology_adapter import load_gnb_site_from_scene
from structure.scene_registry import build_scene


DEFAULT_CASES = [
    ("outdoor_green", Position(420.0, 820.0)),
    ("student_union_center", Position(520.0, 280.0)),
    ("gym_center", Position(860.0, 250.0)),
    ("outdoor_east_of_student_union", Position(700.0, 300.0)),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Debug map-level propagation geometry.")
    parser.add_argument("--scene", default="bristol_topology")
    parser.add_argument("--x", type=float)
    parser.add_argument("--y", type=float)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument(
        "--with-calibration",
        action="store_true",
        help="Explicitly use the configured provisional/confirmed coordinate calibration.",
    )
    parser.add_argument("--gnb-height-m", type=float)
    parser.add_argument("--ue-height-m", type=float)
    args = parser.parse_args()

    scene = build_scene(args.scene)
    gnb = load_gnb_site_from_scene(scene)
    coordinate_view = None
    if args.with_calibration:
        calibration = load_coordinate_calibration(args.scene)
        if calibration is None:
            parser.error(f"No coordinate calibration is configured for scene {args.scene!r}.")
        coordinate_view = coordinate_view_from_calibration(
            calibration,
            gnb_height_m=args.gnb_height_m,
            ue_height_m=args.ue_height_m,
        )

    if args.x is not None and args.y is not None:
        cases = [("custom", Position(args.x, args.y))]
    else:
        cases = DEFAULT_CASES

    reports = []
    for case_id, position in cases:
        geometry = analyze_propagation_geometry(
            scene=scene,
            receiver_position=position,
            gnb=gnb,
            coordinate_view=coordinate_view,
        )
        report = geometry_to_report(geometry)
        report["case_id"] = case_id
        reports.append(report)

    print(json.dumps(reports, ensure_ascii=False, indent=2 if args.pretty else None))


if __name__ == "__main__":
    main()
