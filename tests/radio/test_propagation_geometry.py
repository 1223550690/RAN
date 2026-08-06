from __future__ import annotations

from types import SimpleNamespace
import unittest

from ran.contracts import GnbSite, Position
from ran.radio.geometry import (
    IGNORED_BLOCKING_BUILDING_NLOS,
    IGNORED_DUPLICATE_SURFACE,
    IGNORED_OPEN_PORTAL,
    LINK_INDOOR_DIFFERENT_BUILDING,
    LINK_INDOOR_SAME_BUILDING,
    LINK_INDOOR_TO_OUTDOOR,
    LINK_OUTDOOR_LOS,
    LINK_OUTDOOR_NLOS,
    LINK_OUTDOOR_TO_INDOOR,
    LOS,
    NLOS,
    analyze_propagation_geometry,
)
from ran.radio.topology_adapter import load_gnb_site_from_scene
from structure.scene_registry import build_scene


OUTDOOR = {"space": "outdoor", "area": None, "child_area": None}


def _indoor(area_id: str, child_area_id: str | None = None) -> dict:
    child_area = {"id": child_area_id} if child_area_id else None
    return {
        "space": "indoor",
        "area": {"id": area_id},
        "child_area": child_area,
    }


def _gnb(position: Position | None = None) -> GnbSite:
    return GnbSite(
        gnb_id="gnb_test",
        position=position or Position(0.0, 0.0),
        carrier_freq_mhz=3500.0,
        bandwidth_mhz=100.0,
        tx_power_dbm=30.0,
        total_prbs=273,
        antenna_elements=1,
        mimo_layers=1,
    )


def _wall(
    wall_id: str,
    distance: float,
    *,
    area_id: str | None,
    scope: str = "area",
    wall_type: str = "exterior",
    material: str = "concrete",
) -> dict:
    return {
        "wall_id": wall_id,
        "name": wall_id,
        "scope": scope,
        "wall_type": wall_type,
        "material": material,
        "area_id": area_id,
        "area_name": area_id,
        "segment": ((distance, -5.0), (distance, 5.0)),
        "intersection": (distance, 0.0),
        "distance_from_start": distance,
        "penetration_loss_db": 10.0,
    }


def _portal(
    portal_id: str,
    distance: float,
    *,
    open_: bool,
    wall_id: str | None = None,
    locked: bool = False,
) -> dict:
    return {
        "id": portal_id,
        "name": portal_id,
        "kind": "door",
        "role": "passage",
        "open": open_,
        "locked": locked,
        "wall_id": wall_id,
        "areas": ["outdoor", "building_b"],
        "segment": ((distance, -2.0), (distance, 2.0)),
    }


class _SyntheticMapService:
    def __init__(
        self,
        *,
        gnb_area: dict,
        receiver_area: dict,
        walls: list[dict] | None = None,
    ) -> None:
        self.gnb_area = gnb_area
        self.receiver_area = receiver_area
        self.walls = walls or []

    def get_area_at(self, scene, x: float, y: float) -> dict:
        if x == 0.0 and y == 0.0:
            return self.gnb_area
        return self.receiver_area

    def get_walls_between(self, scene, start, end) -> dict:
        return {"walls": [dict(wall) for wall in self.walls]}


def _analyze(
    *,
    gnb_area: dict = OUTDOOR,
    receiver_area: dict = OUTDOOR,
    walls: list[dict] | None = None,
    portals: list[dict] | None = None,
):
    return analyze_propagation_geometry(
        scene=SimpleNamespace(portals=portals or [], areas=[]),
        receiver_position=Position(100.0, 0.0),
        gnb=_gnb(),
        map_service=_SyntheticMapService(
            gnb_area=gnb_area,
            receiver_area=receiver_area,
            walls=walls,
        ),
    )


class PropagationGeometryClassificationTests(unittest.TestCase):
    def test_outdoor_los_without_crossings(self) -> None:
        geometry = _analyze()

        self.assertEqual(geometry.link_type, LINK_OUTDOOR_LOS)
        self.assertEqual(geometry.los_state, LOS)
        self.assertEqual(geometry.outdoor_distance_map_units, 100.0)
        self.assertEqual(geometry.indoor_distance_map_units, 0.0)
        self.assertEqual(geometry.effective_surface_crossings, [])

    def test_outdoor_nlos_records_blocking_building(self) -> None:
        geometry = _analyze(
            walls=[
                _wall("blocker_west", 40.0, area_id="building_blocker"),
                _wall("blocker_east", 60.0, area_id="building_blocker"),
            ]
        )

        self.assertEqual(geometry.link_type, LINK_OUTDOOR_NLOS)
        self.assertEqual(geometry.los_state, NLOS)
        self.assertEqual(geometry.blocking_building_ids, ["building_blocker"])
        self.assertEqual(geometry.effective_surface_crossings, [])
        self.assertTrue(
            all(
                crossing.ignored_reason == IGNORED_BLOCKING_BUILDING_NLOS
                for crossing in geometry.all_surface_crossings
            )
        )

    def test_outdoor_to_indoor_splits_at_receiver_exterior(self) -> None:
        geometry = _analyze(
            receiver_area=_indoor("building_b", "room_b1"),
            walls=[_wall("building_b_exterior", 60.0, area_id="building_b")],
        )

        self.assertEqual(geometry.link_type, LINK_OUTDOOR_TO_INDOOR)
        self.assertEqual(geometry.los_state, NLOS)
        self.assertEqual(geometry.receiver_building_id, "building_b")
        self.assertEqual(geometry.receiver_child_area_id, "room_b1")
        self.assertEqual(geometry.outdoor_distance_map_units, 60.0)
        self.assertEqual(geometry.indoor_distance_map_units, 40.0)
        self.assertEqual(
            [item.surface_id for item in geometry.exterior_surfaces_crossed],
            ["building_b_exterior"],
        )

    def test_indoor_to_outdoor_splits_at_gnb_exterior(self) -> None:
        geometry = _analyze(
            gnb_area=_indoor("building_a"),
            walls=[_wall("building_a_exterior", 40.0, area_id="building_a")],
        )

        self.assertEqual(geometry.link_type, LINK_INDOOR_TO_OUTDOOR)
        self.assertEqual(geometry.los_state, NLOS)
        self.assertEqual(geometry.indoor_distance_map_units, 40.0)
        self.assertEqual(geometry.outdoor_distance_map_units, 60.0)

    def test_indoor_same_building_is_fully_indoor(self) -> None:
        geometry = _analyze(
            gnb_area=_indoor("building_a"),
            receiver_area=_indoor("building_a", "room_a2"),
        )

        self.assertEqual(geometry.link_type, LINK_INDOOR_SAME_BUILDING)
        self.assertEqual(geometry.los_state, LOS)
        self.assertEqual(geometry.outdoor_distance_map_units, 0.0)
        self.assertEqual(geometry.indoor_distance_map_units, 100.0)

    def test_indoor_different_buildings_splits_both_indoor_legs(self) -> None:
        geometry = _analyze(
            gnb_area=_indoor("building_a"),
            receiver_area=_indoor("building_b"),
            walls=[
                _wall("building_a_exterior", 20.0, area_id="building_a"),
                _wall("building_b_exterior", 80.0, area_id="building_b"),
            ],
        )

        self.assertEqual(geometry.link_type, LINK_INDOOR_DIFFERENT_BUILDING)
        self.assertEqual(geometry.los_state, NLOS)
        self.assertEqual(geometry.indoor_distance_map_units, 40.0)
        self.assertEqual(geometry.outdoor_distance_map_units, 60.0)


class PropagationGeometryWallTests(unittest.TestCase):
    def test_explicit_wall_wins_over_area_boundary_at_same_crossing(self) -> None:
        geometry = _analyze(
            receiver_area=_indoor("building_b"),
            walls=[
                _wall(
                    "building_b_boundary",
                    60.0,
                    area_id="building_b",
                    scope="area_boundary",
                ),
                _wall(
                    "building_b_explicit_wall",
                    60.0,
                    area_id="building_b",
                    scope="area",
                ),
            ],
        )

        self.assertEqual(
            [item.surface_id for item in geometry.effective_surface_crossings],
            ["building_b_explicit_wall"],
        )
        ignored = next(
            item
            for item in geometry.all_surface_crossings
            if item.surface_id == "building_b_boundary"
        )
        self.assertEqual(ignored.ignored_reason, IGNORED_DUPLICATE_SURFACE)

    def test_duplicate_wall_id_is_counted_once(self) -> None:
        geometry = _analyze(
            receiver_area=_indoor("building_b"),
            walls=[
                _wall("building_b_exterior", 60.0, area_id="building_b"),
                _wall("building_b_exterior", 60.2, area_id="building_b"),
            ],
        )

        self.assertEqual(len(geometry.effective_surface_crossings), 1)
        self.assertEqual(
            geometry.effective_surface_crossings[0].surface_id,
            "building_b_exterior",
        )
        self.assertEqual(
            geometry.all_surface_crossings[1].ignored_reason,
            IGNORED_DUPLICATE_SURFACE,
        )

    def test_exterior_and_interior_crossings_remain_ordered(self) -> None:
        geometry = _analyze(
            receiver_area=_indoor("building_b"),
            walls=[
                _wall("building_b_exterior", 30.0, area_id="building_b"),
                _wall(
                    "room_wall_1",
                    50.0,
                    area_id="building_b",
                    wall_type="interior",
                ),
                _wall(
                    "room_wall_2",
                    70.0,
                    area_id="building_b",
                    wall_type="interior",
                ),
            ],
        )

        self.assertEqual(
            [item.surface_id for item in geometry.exterior_surfaces_crossed],
            ["building_b_exterior"],
        )
        self.assertEqual(
            [item.surface_id for item in geometry.interior_walls_crossed],
            ["room_wall_1", "room_wall_2"],
        )
        self.assertEqual(
            [item.distance_from_gnb_map_units for item in geometry.effective_surface_crossings],
            [30.0, 50.0, 70.0],
        )

    def test_non_target_building_is_blocker_not_material_penetration(self) -> None:
        geometry = _analyze(
            receiver_area=_indoor("building_b"),
            walls=[
                _wall("blocker_west", 20.0, area_id="building_blocker"),
                _wall("blocker_east", 40.0, area_id="building_blocker"),
                _wall("building_b_exterior", 80.0, area_id="building_b"),
            ],
        )

        self.assertEqual(geometry.link_type, LINK_OUTDOOR_TO_INDOOR)
        self.assertEqual(geometry.blocking_building_ids, ["building_blocker"])
        self.assertEqual(
            [item.surface_id for item in geometry.effective_surface_crossings],
            ["building_b_exterior"],
        )
        blocker_crossings = [
            item
            for item in geometry.all_surface_crossings
            if item.area_id == "building_blocker"
        ]
        self.assertTrue(
            all(
                item.ignored_reason == IGNORED_BLOCKING_BUILDING_NLOS
                for item in blocker_crossings
            )
        )


class PropagationGeometryPortalTests(unittest.TestCase):
    def test_open_portal_with_wall_id_disables_matching_surface(self) -> None:
        geometry = _analyze(
            walls=[_wall("entrance_wall", 50.0, area_id="building_blocker")],
            portals=[
                _portal(
                    "entrance",
                    30.0,
                    open_=True,
                    wall_id="entrance_wall",
                )
            ],
        )

        self.assertEqual(geometry.link_type, LINK_OUTDOOR_LOS)
        self.assertEqual(geometry.los_state, LOS)
        self.assertEqual(len(geometry.portals_crossed), 1)
        self.assertEqual(
            geometry.all_surface_crossings[0].ignored_reason,
            IGNORED_OPEN_PORTAL,
        )

    def test_closed_portal_does_not_remove_surface_from_classification(self) -> None:
        geometry = _analyze(
            walls=[_wall("entrance_wall", 50.0, area_id="building_blocker")],
            portals=[
                _portal(
                    "entrance",
                    50.0,
                    open_=False,
                    wall_id="entrance_wall",
                )
            ],
        )

        self.assertEqual(geometry.link_type, LINK_OUTDOOR_NLOS)
        self.assertEqual(geometry.los_state, NLOS)
        self.assertEqual(geometry.blocking_building_ids, ["building_blocker"])
        self.assertEqual(
            geometry.all_surface_crossings[0].ignored_reason,
            IGNORED_BLOCKING_BUILDING_NLOS,
        )
        self.assertFalse(geometry.portals_crossed[0].open)

    def test_open_portal_without_wall_id_matches_by_intersection(self) -> None:
        geometry = _analyze(
            walls=[_wall("entrance_wall", 50.0, area_id="building_blocker")],
            portals=[_portal("entrance", 50.0, open_=True)],
        )

        self.assertEqual(geometry.link_type, LINK_OUTDOOR_LOS)
        self.assertEqual(
            geometry.all_surface_crossings[0].ignored_reason,
            IGNORED_OPEN_PORTAL,
        )

    def test_open_portal_at_different_intersection_does_not_disable_wall(self) -> None:
        geometry = _analyze(
            walls=[_wall("entrance_wall", 60.0, area_id="building_blocker")],
            portals=[_portal("other_door", 50.0, open_=True)],
        )

        self.assertEqual(geometry.link_type, LINK_OUTDOOR_NLOS)
        self.assertEqual(geometry.blocking_building_ids, ["building_blocker"])
        self.assertEqual(
            geometry.all_surface_crossings[0].ignored_reason,
            IGNORED_BLOCKING_BUILDING_NLOS,
        )
        self.assertEqual(geometry.portals_crossed[0].portal_id, "other_door")

    def test_locked_open_portal_still_uses_rf_open_state(self) -> None:
        geometry = _analyze(
            walls=[_wall("entrance_wall", 50.0, area_id="building_blocker")],
            portals=[
                _portal(
                    "locked_but_open",
                    50.0,
                    open_=True,
                    wall_id="entrance_wall",
                    locked=True,
                )
            ],
        )

        self.assertEqual(geometry.link_type, LINK_OUTDOOR_LOS)
        self.assertTrue(geometry.portals_crossed[0].locked)
        self.assertEqual(
            geometry.all_surface_crossings[0].ignored_reason,
            IGNORED_OPEN_PORTAL,
        )


class BristolPropagationGeometrySmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.scene = build_scene("bristol_topology")
        cls.gnb = load_gnb_site_from_scene(cls.scene)

    def test_representative_bristol_links_keep_expected_classification(self) -> None:
        cases = [
            ("outdoor_green", Position(420.0, 820.0), LINK_OUTDOOR_LOS, LOS),
            (
                "student_union_center",
                Position(520.0, 280.0),
                LINK_OUTDOOR_TO_INDOOR,
                NLOS,
            ),
            (
                "gym_center",
                Position(860.0, 250.0),
                LINK_OUTDOOR_TO_INDOOR,
                NLOS,
            ),
            (
                "outdoor_east_of_student_union",
                Position(700.0, 300.0),
                LINK_OUTDOOR_NLOS,
                NLOS,
            ),
        ]

        for case_id, position, expected_link, expected_los in cases:
            with self.subTest(case_id=case_id):
                geometry = analyze_propagation_geometry(
                    scene=self.scene,
                    receiver_position=position,
                    gnb=self.gnb,
                )
                self.assertEqual(geometry.link_type, expected_link)
                self.assertEqual(geometry.los_state, expected_los)

    def test_gym_link_records_student_union_as_blocker(self) -> None:
        geometry = analyze_propagation_geometry(
            scene=self.scene,
            receiver_position=Position(860.0, 250.0),
            gnb=self.gnb,
        )

        self.assertIn("block_09_student_union", geometry.blocking_building_ids)


if __name__ == "__main__":
    unittest.main()
