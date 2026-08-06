from __future__ import annotations

from types import SimpleNamespace
import unittest

from ran.contracts import GnbSite, Position
from ran.radio.coordinate_calibration import (
    CalibrationDefinition,
    resolve_coordinate_calibration,
)
from ran.radio.geometry import (
    CoordinateCalibrationView,
    analyze_propagation_geometry,
    coordinate_view_from_calibration,
)


def _gnb() -> GnbSite:
    return GnbSite(
        gnb_id="gnb_test",
        position=Position(0.0, 0.0),
        carrier_freq_mhz=3500.0,
        bandwidth_mhz=100.0,
        tx_power_dbm=30.0,
        total_prbs=273,
        antenna_elements=1,
        mimo_layers=1,
    )


def _calibration():
    return resolve_coordinate_calibration(
        CalibrationDefinition(
            scene_id="test_scene",
            calibration_id="test_v0",
            status="provisional",
            source="unit_test",
            map_bounds=(0.0, 0.0, 2000.0, 2000.0),
            physical_width_m=300.0,
            physical_height_m=400.0,
            origin_map=(0.0, 0.0),
            y_axis_direction="down",
            gnb_height_m=None,
            default_ue_height_m=1.5,
        )
    )


class _OutdoorMapService:
    def get_area_at(self, scene, x: float, y: float) -> dict:
        return {"space": "outdoor", "area": None, "child_area": None}

    def get_walls_between(self, scene, start, end) -> dict:
        return {"walls": []}


class _OutdoorToIndoorMapService:
    def get_area_at(self, scene, x: float, y: float) -> dict:
        if x == 0.0 and y == 0.0:
            return {"space": "outdoor", "area": None, "child_area": None}
        return {
            "space": "indoor",
            "area": {"id": "building_test"},
            "child_area": None,
        }

    def get_walls_between(self, scene, start, end) -> dict:
        return {
            "walls": [
                {
                    "wall_id": "building_test_west",
                    "scope": "area",
                    "wall_type": "exterior",
                    "material": "brick",
                    "area_id": "building_test",
                    "area_name": "Test Building",
                    "segment": ((50.0, 0.0), (50.0, 100.0)),
                    "intersection": (50.0, 50.0),
                    "distance_from_start": 50.0 * 2.0**0.5,
                    "penetration_loss_db": 12.0,
                }
            ]
        }


class GeometryCoordinateCalibrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scene = SimpleNamespace(portals=[], areas=[])

    def test_no_calibration_preserves_optional_meter_fields(self) -> None:
        geometry = analyze_propagation_geometry(
            scene=self.scene,
            receiver_position=Position(100.0, 100.0),
            gnb=_gnb(),
            map_service=_OutdoorMapService(),
        )

        self.assertIsNone(geometry.distance.distance_2d_m)
        self.assertIsNone(geometry.distance.distance_3d_m)
        self.assertIsNone(geometry.outdoor_distance_m)
        self.assertIsNone(geometry.indoor_distance_m)

    def test_legacy_scalar_view_remains_compatible(self) -> None:
        view = CoordinateCalibrationView(2.0, 10.0, 4.0)
        geometry = analyze_propagation_geometry(
            scene=self.scene,
            receiver_position=Position(3.0, 4.0),
            gnb=_gnb(),
            coordinate_view=view,
            map_service=_OutdoorMapService(),
        )

        self.assertAlmostEqual(geometry.distance.distance_2d_m or 0.0, 10.0)
        self.assertAlmostEqual(geometry.distance.distance_3d_m or 0.0, 136.0**0.5)
        self.assertAlmostEqual(geometry.outdoor_distance_m or 0.0, 10.0)
        self.assertEqual(geometry.indoor_distance_m, 0.0)

    def test_anisotropic_scales_take_precedence_over_legacy_scalar(self) -> None:
        view = CoordinateCalibrationView(
            meters_per_map_unit=9.0,
            meters_per_map_unit_x=0.15,
            meters_per_map_unit_y=0.20,
        )
        geometry = analyze_propagation_geometry(
            scene=self.scene,
            receiver_position=Position(100.0, 100.0),
            gnb=_gnb(),
            coordinate_view=view,
            map_service=_OutdoorMapService(),
        )

        self.assertAlmostEqual(geometry.distance.distance_2d_m or 0.0, 25.0)
        self.assertAlmostEqual(geometry.outdoor_distance_m or 0.0, 25.0)

    def test_adapter_uses_calibration_scales_and_default_ue_height(self) -> None:
        view = coordinate_view_from_calibration(_calibration(), gnb_height_m=10.0)

        self.assertIsNone(view.meters_per_map_unit)
        self.assertAlmostEqual(view.meters_per_map_unit_x or 0.0, 0.15)
        self.assertAlmostEqual(view.meters_per_map_unit_y or 0.0, 0.20)
        self.assertEqual(view.gnb_height_m, 10.0)
        self.assertEqual(view.ue_height_m, 1.5)

    def test_anisotropic_crossing_and_o2i_split_use_link_direction(self) -> None:
        view = coordinate_view_from_calibration(
            _calibration(),
            gnb_height_m=10.0,
        )
        geometry = analyze_propagation_geometry(
            scene=self.scene,
            receiver_position=Position(100.0, 100.0),
            gnb=_gnb(),
            coordinate_view=view,
            map_service=_OutdoorToIndoorMapService(),
        )

        self.assertAlmostEqual(geometry.distance.distance_2d_m or 0.0, 25.0)
        self.assertAlmostEqual(geometry.all_surface_crossings[0].distance_from_gnb_m or 0.0, 12.5)
        self.assertAlmostEqual(geometry.outdoor_distance_m or 0.0, 12.5)
        self.assertAlmostEqual(geometry.indoor_distance_m or 0.0, 12.5)
        self.assertAlmostEqual(
            (geometry.outdoor_distance_m or 0.0)
            + (geometry.indoor_distance_m or 0.0),
            geometry.distance.distance_2d_m or 0.0,
        )


if __name__ == "__main__":
    unittest.main()
