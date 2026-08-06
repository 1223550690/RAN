from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from ran.contracts import Position
from ran.radio.coordinate_calibration import (
    CalibrationAnchor,
    CalibrationConfigError,
    CalibrationDefinition,
    distance_2d_m,
    distance_3d_m,
    load_calibration_definition,
    load_coordinate_calibration,
    map_position_to_meters,
    resolve_coordinate_calibration,
)


def _definition(
    *,
    physical_width_m: float = 300.0,
    physical_height_m: float = 400.0,
    status: str = "provisional",
    y_axis_direction: str = "down",
    anchors: tuple[CalibrationAnchor, ...] = (),
) -> CalibrationDefinition:
    return CalibrationDefinition(
        scene_id="test_scene",
        calibration_id="test_v0",
        status=status,
        source="unit_test",
        map_bounds=(0.0, 0.0, 2000.0, 2000.0),
        physical_width_m=physical_width_m,
        physical_height_m=physical_height_m,
        origin_map=(0.0, 0.0),
        y_axis_direction=y_axis_direction,
        gnb_height_m=None,
        default_ue_height_m=1.5,
        anchors=anchors,
    )


class CoordinateCalibrationTests(unittest.TestCase):
    def test_provisional_bristol_extent_produces_independent_scales(self) -> None:
        calibration = resolve_coordinate_calibration(_definition())

        self.assertAlmostEqual(calibration.meters_per_map_unit_x, 0.15)
        self.assertAlmostEqual(calibration.meters_per_map_unit_y, 0.20)
        self.assertIsNone(calibration.meters_per_map_unit)
        self.assertEqual(calibration.status, "provisional")

    def test_changing_extent_changes_scale_without_algorithm_changes(self) -> None:
        calibration = resolve_coordinate_calibration(
            _definition(physical_width_m=320.0, physical_height_m=420.0)
        )

        self.assertAlmostEqual(calibration.meters_per_map_unit_x, 0.16)
        self.assertAlmostEqual(calibration.meters_per_map_unit_y, 0.21)

    def test_anisotropic_horizontal_vertical_and_diagonal_distances(self) -> None:
        calibration = resolve_coordinate_calibration(_definition())
        origin = Position(0.0, 0.0)

        self.assertAlmostEqual(distance_2d_m(origin, Position(100.0, 0.0), calibration), 15.0)
        self.assertAlmostEqual(distance_2d_m(origin, Position(0.0, 100.0), calibration), 20.0)
        self.assertAlmostEqual(distance_2d_m(origin, Position(100.0, 100.0), calibration), 25.0)

    def test_same_point_distance_is_zero(self) -> None:
        calibration = resolve_coordinate_calibration(_definition())
        point = Position(25.0, 30.0)

        self.assertEqual(distance_2d_m(point, point, calibration), 0.0)

    def test_uniform_extent_exposes_legacy_scalar(self) -> None:
        calibration = resolve_coordinate_calibration(
            _definition(physical_width_m=300.0, physical_height_m=300.0)
        )

        self.assertAlmostEqual(calibration.meters_per_map_unit_x, 0.15)
        self.assertAlmostEqual(calibration.meters_per_map_unit_y, 0.15)
        self.assertAlmostEqual(calibration.meters_per_map_unit or 0.0, 0.15)

    def test_cartesian_y_axis_flips_physical_coordinate(self) -> None:
        calibration = resolve_coordinate_calibration(
            _definition(y_axis_direction="up")
        )

        physical = map_position_to_meters(Position(100.0, 100.0), calibration)

        self.assertAlmostEqual(physical.x_m, 15.0)
        self.assertAlmostEqual(physical.y_m, -20.0)

    def test_distance_3d_uses_explicit_heights(self) -> None:
        calibration = resolve_coordinate_calibration(_definition())

        distance = distance_3d_m(
            Position(0.0, 0.0),
            Position(20.0, 0.0),
            calibration,
            start_height_m=4.0,
            end_height_m=0.0,
        )

        self.assertAlmostEqual(distance, 5.0)

    def test_identical_anchor_points_are_rejected(self) -> None:
        anchor = CalibrationAnchor(
            anchor_id="bad",
            map_start=(1.0, 1.0),
            map_end=(1.0, 1.0),
            known_distance_m=1.0,
            source="unit_test",
        )

        with self.assertRaisesRegex(CalibrationConfigError, "identical map points"):
            resolve_coordinate_calibration(_definition(anchors=(anchor,)))

    def test_direct_definition_with_invalid_status_is_rejected(self) -> None:
        with self.assertRaisesRegex(CalibrationConfigError, "status"):
            resolve_coordinate_calibration(
                _definition(status="not_a_calibration_status")
            )

    def test_confirmed_calibration_requires_two_anchors(self) -> None:
        anchor = CalibrationAnchor(
            anchor_id="one",
            map_start=(0.0, 0.0),
            map_end=(100.0, 0.0),
            known_distance_m=15.0,
            source="unit_test",
        )

        with self.assertRaisesRegex(CalibrationConfigError, "at least two"):
            resolve_coordinate_calibration(
                _definition(status="confirmed", anchors=(anchor,))
            )

    def test_confirmed_calibration_rejects_large_anchor_error(self) -> None:
        anchors = (
            CalibrationAnchor(
                anchor_id="horizontal",
                map_start=(0.0, 0.0),
                map_end=(100.0, 0.0),
                known_distance_m=30.0,
                source="unit_test",
            ),
            CalibrationAnchor(
                anchor_id="vertical",
                map_start=(0.0, 0.0),
                map_end=(0.0, 100.0),
                known_distance_m=40.0,
                source="unit_test",
            ),
        )

        with self.assertRaisesRegex(CalibrationConfigError, "relative error"):
            resolve_coordinate_calibration(
                _definition(status="confirmed", anchors=anchors)
            )

    def test_unknown_scene_returns_none(self) -> None:
        self.assertIsNone(load_calibration_definition("not_configured"))
        self.assertIsNone(load_coordinate_calibration("not_configured"))

    def test_default_config_loads_as_provisional(self) -> None:
        calibration = load_coordinate_calibration("bristol_topology")

        self.assertIsNotNone(calibration)
        assert calibration is not None
        self.assertEqual(
            calibration.calibration_id,
            "bristol_topology_uniform_extent_v1",
        )
        self.assertAlmostEqual(calibration.meters_per_map_unit_x, 0.1375)
        self.assertAlmostEqual(calibration.meters_per_map_unit_y, 0.1375)
        self.assertAlmostEqual(calibration.meters_per_map_unit, 0.1375)

    def test_loader_rejects_partial_or_invalid_extent(self) -> None:
        data = {
            "schema_version": "1",
            "scenes": {
                "test_scene": {
                    "calibration_id": "bad",
                    "status": "provisional",
                    "source": "unit_test",
                    "map_bounds": [0, 0, 2000, 2000],
                    "physical_extent_m": {"width": 300},
                    "origin_map": [0, 0],
                    "y_axis_direction": "down",
                }
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "calibration.json"
            path.write_text(json.dumps(data), encoding="utf-8")

            with self.assertRaisesRegex(CalibrationConfigError, "height"):
                load_calibration_definition("test_scene", path)


if __name__ == "__main__":
    unittest.main()
