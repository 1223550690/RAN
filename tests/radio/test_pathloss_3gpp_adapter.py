from __future__ import annotations

from dataclasses import asdict
import math
import unittest

from ran.contracts import GnbSite, Position
from ran.radio.geometry import (
    LINK_INDOOR_DIFFERENT_BUILDING,
    LINK_INDOOR_SAME_BUILDING,
    LINK_INDOOR_TO_OUTDOOR,
    LINK_OUTDOOR_LOS,
    LINK_OUTDOOR_NLOS,
    LINK_OUTDOOR_TO_INDOOR,
    LOS,
    NLOS,
    LinkDistance,
    PropagationGeometry,
    PropagationSurfaceCrossing,
)
from ran.radio.pathloss_3gpp import (
    SCENARIO_INH_OFFICE,
    SCENARIO_UMI_STREET_CANYON,
)
from ran.radio.pathloss_3gpp_adapter import (
    InconsistentGeometryLinkError,
    MissingCalibratedDistanceError,
    UnsupportedGeometryLinkError,
    o2i_path_loss_request_from_geometry,
    path_loss_request_from_geometry,
)
from ran.radio.pathloss_3gpp_o2i import LOW_LOSS


def _gnb() -> GnbSite:
    return GnbSite(
        gnb_id="gnb_test",
        position=Position(0.0, 0.0),
        carrier_freq_mhz=3500.0,
        bandwidth_mhz=100.0,
        tx_power_dbm=30.0,
        total_prbs=273,
        antenna_elements=4,
        mimo_layers=2,
    )


def _geometry(
    *,
    link_type: str,
    los_state: str,
    distance_2d_m: float | None = 100.0,
    distance_3d_m: float | None = None,
) -> PropagationGeometry:
    if distance_3d_m is None and distance_2d_m is not None:
        distance_3d_m = math.hypot(distance_2d_m, 8.5)
    return PropagationGeometry(
        gnb_id="gnb_test",
        receiver_position=Position(100.0, 0.0),
        receiver_space="indoor" if "indoor" in link_type else "outdoor",
        receiver_area_id=None,
        receiver_child_area_id=None,
        receiver_building_id=None,
        gnb_space="outdoor",
        gnb_area_id=None,
        link_type=link_type,
        los_state=los_state,
        distance=LinkDistance(
            map_distance_units=100.0,
            distance_2d_m=distance_2d_m,
            distance_3d_m=distance_3d_m,
        ),
        outdoor_distance_map_units=100.0,
        indoor_distance_map_units=0.0,
        outdoor_distance_m=distance_2d_m,
        indoor_distance_m=0.0 if distance_2d_m is not None else None,
        blocking_building_ids=[],
        exterior_surfaces_crossed=[],
        interior_walls_crossed=[],
        portals_crossed=[],
        all_surface_crossings=[],
        effective_surface_crossings=[],
    )


def _o2i_geometry(*, blocking_building_ids: list[str] | None = None):
    geometry = _geometry(
        link_type=LINK_OUTDOOR_TO_INDOOR,
        los_state=NLOS,
    )
    geometry.receiver_building_id = "target_building"
    geometry.indoor_distance_m = 20.0
    geometry.outdoor_distance_m = 80.0
    exterior = PropagationSurfaceCrossing(
        surface_id="target_exterior",
        name="Target exterior",
        scope="exterior",
        wall_type="external",
        material="brick",
        area_id="target_building",
        area_name="Target building",
        intersection=(80.0, 0.0),
        distance_from_gnb_map_units=80.0,
        penetration_loss_db=99.0,
        segment=((80.0, -10.0), (80.0, 10.0)),
        distance_from_gnb_m=80.0,
    )
    geometry.exterior_surfaces_crossed = [exterior]
    geometry.effective_surface_crossings = [exterior]
    geometry.all_surface_crossings = [exterior]
    geometry.blocking_building_ids = list(blocking_building_ids or [])
    return geometry


class GeometryPathLossAdapterTests(unittest.TestCase):
    def test_o2i_adapter_uses_los_without_external_blocker(self) -> None:
        request = o2i_path_loss_request_from_geometry(
            geometry=_o2i_geometry(),
            gnb=_gnb(),
            bs_height_m=10.0,
            ut_height_m=1.5,
            penetration_model=LOW_LOSS,
        )

        self.assertEqual(request.basic_outdoor_request.los_state, LOS)
        self.assertEqual(request.indoor_distance_m, 20.0)
        self.assertEqual(request.indoor_distance_source, "geometry_measured")

    def test_o2i_adapter_uses_nlos_when_another_building_blocks(self) -> None:
        request = o2i_path_loss_request_from_geometry(
            geometry=_o2i_geometry(blocking_building_ids=["blocker"]),
            gnb=_gnb(),
            bs_height_m=10.0,
            ut_height_m=1.5,
            penetration_model=LOW_LOSS,
        )

        self.assertEqual(request.basic_outdoor_request.los_state, NLOS)

    def test_o2i_adapter_does_not_copy_raw_map_wall_loss(self) -> None:
        request = o2i_path_loss_request_from_geometry(
            geometry=_o2i_geometry(),
            gnb=_gnb(),
            bs_height_m=10.0,
            ut_height_m=1.5,
            penetration_model=LOW_LOSS,
        )

        self.assertFalse(hasattr(request, "penetration_loss_db"))

    def test_o2i_adapter_rejects_non_o2i_link(self) -> None:
        with self.assertRaises(UnsupportedGeometryLinkError):
            o2i_path_loss_request_from_geometry(
                geometry=_geometry(link_type=LINK_OUTDOOR_LOS, los_state=LOS),
                gnb=_gnb(),
                bs_height_m=10.0,
                ut_height_m=1.5,
                penetration_model=LOW_LOSS,
            )

    def test_outdoor_los_maps_to_umi_los(self) -> None:
        request = path_loss_request_from_geometry(
            geometry=_geometry(link_type=LINK_OUTDOOR_LOS, los_state=LOS),
            gnb=_gnb(),
            bs_height_m=10.0,
            ut_height_m=1.5,
        )

        self.assertEqual(request.scenario, SCENARIO_UMI_STREET_CANYON)
        self.assertEqual(request.los_state, LOS)

    def test_outdoor_nlos_maps_to_umi_nlos(self) -> None:
        request = path_loss_request_from_geometry(
            geometry=_geometry(link_type=LINK_OUTDOOR_NLOS, los_state=NLOS),
            gnb=_gnb(),
            bs_height_m=10.0,
            ut_height_m=1.5,
        )

        self.assertEqual(request.scenario, SCENARIO_UMI_STREET_CANYON)
        self.assertEqual(request.los_state, NLOS)

    def test_same_building_indoor_maps_to_inh_for_both_los_states(self) -> None:
        for los_state in (LOS, NLOS):
            with self.subTest(los_state=los_state):
                request = path_loss_request_from_geometry(
                    geometry=_geometry(
                        link_type=LINK_INDOOR_SAME_BUILDING,
                        los_state=los_state,
                        distance_2d_m=math.sqrt(96.0),
                        distance_3d_m=10.0,
                    ),
                    gnb=_gnb(),
                    bs_height_m=3.0,
                    ut_height_m=1.0,
                )

                self.assertEqual(request.scenario, SCENARIO_INH_OFFICE)
                self.assertEqual(request.los_state, los_state)

    def test_missing_meter_distance_is_rejected(self) -> None:
        missing_2d = _geometry(
            link_type=LINK_OUTDOOR_LOS,
            los_state=LOS,
            distance_2d_m=None,
            distance_3d_m=100.0,
        )
        missing_3d = _geometry(
            link_type=LINK_OUTDOOR_LOS,
            los_state=LOS,
        )
        missing_3d.distance.distance_3d_m = None

        cases = (missing_2d, missing_3d)
        for geometry in cases:
            with self.subTest(distance=geometry.distance):
                with self.assertRaises(MissingCalibratedDistanceError):
                    path_loss_request_from_geometry(
                        geometry=geometry,
                        gnb=_gnb(),
                        bs_height_m=10.0,
                        ut_height_m=1.5,
                    )

    def test_complex_links_are_explicitly_unsupported(self) -> None:
        for link_type in (
            LINK_OUTDOOR_TO_INDOOR,
            LINK_INDOOR_TO_OUTDOOR,
            LINK_INDOOR_DIFFERENT_BUILDING,
        ):
            with self.subTest(link_type=link_type):
                with self.assertRaises(UnsupportedGeometryLinkError):
                    path_loss_request_from_geometry(
                        geometry=_geometry(link_type=link_type, los_state=NLOS),
                        gnb=_gnb(),
                        bs_height_m=10.0,
                        ut_height_m=1.5,
                    )

    def test_frequency_and_endpoint_heights_are_not_reinterpreted(self) -> None:
        request = path_loss_request_from_geometry(
            geometry=_geometry(link_type=LINK_OUTDOOR_LOS, los_state=LOS),
            gnb=_gnb(),
            bs_height_m=12.0,
            ut_height_m=1.7,
        )

        self.assertEqual(request.carrier_frequency_mhz, 3500.0)
        self.assertEqual(request.bs_height_m, 12.0)
        self.assertEqual(request.ut_height_m, 1.7)

    def test_contradictory_outdoor_link_state_is_rejected(self) -> None:
        with self.assertRaises(InconsistentGeometryLinkError):
            path_loss_request_from_geometry(
                geometry=_geometry(link_type=LINK_OUTDOOR_LOS, los_state=NLOS),
                gnb=_gnb(),
                bs_height_m=10.0,
                ut_height_m=1.5,
            )

    def test_geometry_and_gnb_ids_must_match(self) -> None:
        geometry = _geometry(link_type=LINK_OUTDOOR_LOS, los_state=LOS)
        geometry.gnb_id = "different_gnb"

        with self.assertRaisesRegex(InconsistentGeometryLinkError, "gnb_id"):
            path_loss_request_from_geometry(
                geometry=geometry,
                gnb=_gnb(),
                bs_height_m=10.0,
                ut_height_m=1.5,
            )

    def test_adapter_does_not_mutate_geometry(self) -> None:
        geometry = _geometry(link_type=LINK_OUTDOOR_LOS, los_state=LOS)
        before = asdict(geometry)

        path_loss_request_from_geometry(
            geometry=geometry,
            gnb=_gnb(),
            bs_height_m=10.0,
            ut_height_m=1.5,
        )

        self.assertEqual(asdict(geometry), before)


if __name__ == "__main__":
    unittest.main()
