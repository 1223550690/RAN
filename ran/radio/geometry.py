from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
import math
from typing import Any

from ran.contracts import GnbSite, Position
from services.map_service import MapService


LINK_OUTDOOR_LOS = "outdoor_los"
LINK_OUTDOOR_NLOS = "outdoor_nlos"
LINK_OUTDOOR_TO_INDOOR = "outdoor_to_indoor"
LINK_INDOOR_TO_OUTDOOR = "indoor_to_outdoor"
LINK_INDOOR_SAME_BUILDING = "indoor_same_building"
LINK_INDOOR_DIFFERENT_BUILDING = "indoor_different_building"

LOS = "los"
NLOS = "nlos"

IGNORED_DUPLICATE_SURFACE = "duplicate_surface"
IGNORED_OPEN_PORTAL = "open_portal"
IGNORED_BLOCKING_BUILDING_NLOS = "blocking_building_nlos_classification"

INTERSECTION_TOLERANCE_MAP_UNITS = 0.5


@dataclass(slots=True)
class CoordinateCalibrationView:
    """Read-only coordinate calibration result owned by the calibration work."""

    meters_per_map_unit: float | None = None
    gnb_height_m: float | None = None
    ue_height_m: float | None = None


@dataclass(slots=True)
class LinkDistance:
    map_distance_units: float
    distance_2d_m: float | None = None
    distance_3d_m: float | None = None


@dataclass(slots=True)
class PropagationSurfaceCrossing:
    surface_id: str
    name: str | None
    scope: str
    wall_type: str | None
    material: str | None
    area_id: str | None
    area_name: str | None
    intersection: tuple[float, float]
    distance_from_gnb_map_units: float
    penetration_loss_db: float
    segment: tuple[tuple[float, float], tuple[float, float]]
    distance_from_gnb_m: float | None = None
    is_effective: bool = True
    ignored_reason: str | None = None


@dataclass(slots=True)
class PortalCrossing:
    portal_id: str
    name: str | None
    kind: str | None
    role: str | None
    open: bool
    locked: bool
    wall_id: str | None
    areas: tuple[str, str] | None
    segment: tuple[tuple[float, float], tuple[float, float]]
    intersection: tuple[float, float] | None
    distance_from_gnb_map_units: float | None
    distance_from_gnb_m: float | None = None


@dataclass(slots=True)
class PropagationGeometry:
    gnb_id: str
    receiver_position: Position
    receiver_space: str
    receiver_area_id: str | None
    receiver_child_area_id: str | None
    receiver_building_id: str | None
    gnb_space: str
    gnb_area_id: str | None
    link_type: str
    los_state: str
    distance: LinkDistance
    outdoor_distance_map_units: float
    indoor_distance_map_units: float
    outdoor_distance_m: float | None
    indoor_distance_m: float | None
    blocking_building_ids: list[str]
    exterior_surfaces_crossed: list[PropagationSurfaceCrossing]
    interior_walls_crossed: list[PropagationSurfaceCrossing]
    portals_crossed: list[PortalCrossing]
    all_surface_crossings: list[PropagationSurfaceCrossing]
    effective_surface_crossings: list[PropagationSurfaceCrossing]


def analyze_propagation_geometry(
    *,
    scene,
    receiver_position: Position,
    gnb: GnbSite,
    coordinate_view: CoordinateCalibrationView | None = None,
    map_service: MapService | None = None,
) -> PropagationGeometry:
    """Analyze map-level propagation geometry for a single gNB-to-receiver link."""

    service = map_service or MapService()
    start = (float(gnb.position.x), float(gnb.position.y))
    end = (float(receiver_position.x), float(receiver_position.y))
    link_distance = _link_distance(start, end, coordinate_view)

    gnb_area = service.get_area_at(scene, start[0], start[1])
    receiver_area = service.get_area_at(scene, end[0], end[1])

    gnb_space = _space(gnb_area)
    receiver_space = _space(receiver_area)
    gnb_area_id = _area_id(gnb_area)
    receiver_area_id = _area_id(receiver_area)
    receiver_child_area_id = _child_area_id(receiver_area)
    receiver_building_id = receiver_area_id if receiver_space == "indoor" else None

    walls_result = service.get_walls_between(scene, start, end)
    all_crossings = _normalize_wall_crossings(
        walls_result.get("walls", []),
        coordinate_view=coordinate_view,
    )
    _deduplicate_crossings(all_crossings)

    portals_crossed = _portal_crossings(
        scene,
        start,
        end,
        coordinate_view=coordinate_view,
    )
    _apply_open_portals(all_crossings, portals_crossed)

    pre_context_effective_crossings = [
        crossing for crossing in all_crossings if crossing.is_effective
    ]

    link_type = _classify_link(
        gnb_space=gnb_space,
        receiver_space=receiver_space,
        gnb_area_id=gnb_area_id,
        receiver_area_id=receiver_area_id,
        effective_crossings=pre_context_effective_crossings,
    )
    blocking_building_ids = _blocking_buildings(
        candidate_crossings=pre_context_effective_crossings,
        link_type=link_type,
        receiver_building_id=receiver_building_id,
        gnb_area_id=gnb_area_id,
    )
    _apply_link_context_filter(
        link_type=link_type,
        gnb_area_id=gnb_area_id,
        receiver_building_id=receiver_building_id,
        crossings=all_crossings,
    )

    effective_crossings = [crossing for crossing in all_crossings if crossing.is_effective]
    exterior_crossings = [_is_exterior(crossing) for crossing in effective_crossings]
    exterior_crossings = [crossing for crossing in exterior_crossings if crossing is not None]
    interior_crossings = [_is_interior(crossing) for crossing in effective_crossings]
    interior_crossings = [crossing for crossing in interior_crossings if crossing is not None]
    los_state = LOS if not effective_crossings else NLOS
    if link_type == LINK_OUTDOOR_NLOS or blocking_building_ids:
        los_state = NLOS

    outdoor_map, indoor_map = _split_indoor_outdoor_distance(
        link_type=link_type,
        total_map_distance=link_distance.map_distance_units,
        gnb_area_id=gnb_area_id,
        receiver_building_id=receiver_building_id,
        effective_crossings=effective_crossings,
        all_crossings=all_crossings,
    )
    outdoor_m = _map_units_to_meters(outdoor_map, coordinate_view)
    indoor_m = _map_units_to_meters(indoor_map, coordinate_view)

    return PropagationGeometry(
        gnb_id=gnb.gnb_id,
        receiver_position=receiver_position,
        receiver_space=receiver_space,
        receiver_area_id=receiver_area_id,
        receiver_child_area_id=receiver_child_area_id,
        receiver_building_id=receiver_building_id,
        gnb_space=gnb_space,
        gnb_area_id=gnb_area_id,
        link_type=link_type,
        los_state=los_state,
        distance=link_distance,
        outdoor_distance_map_units=outdoor_map,
        indoor_distance_map_units=indoor_map,
        outdoor_distance_m=outdoor_m,
        indoor_distance_m=indoor_m,
        blocking_building_ids=blocking_building_ids,
        exterior_surfaces_crossed=exterior_crossings,
        interior_walls_crossed=interior_crossings,
        portals_crossed=portals_crossed,
        all_surface_crossings=all_crossings,
        effective_surface_crossings=effective_crossings,
    )


def geometry_to_report(geometry: PropagationGeometry) -> dict:
    """Return a JSON-friendly propagation geometry report."""

    return {
        "gnb_id": geometry.gnb_id,
        "receiver_position": {
            "x": geometry.receiver_position.x,
            "y": geometry.receiver_position.y,
        },
        "receiver_space": geometry.receiver_space,
        "receiver_area_id": geometry.receiver_area_id,
        "receiver_child_area_id": geometry.receiver_child_area_id,
        "receiver_building_id": geometry.receiver_building_id,
        "gnb_space": geometry.gnb_space,
        "gnb_area_id": geometry.gnb_area_id,
        "link_type": geometry.link_type,
        "los_state": geometry.los_state,
        "map_distance_units": geometry.distance.map_distance_units,
        "distance_2d_m": geometry.distance.distance_2d_m,
        "distance_3d_m": geometry.distance.distance_3d_m,
        "outdoor_distance_map_units": geometry.outdoor_distance_map_units,
        "indoor_distance_map_units": geometry.indoor_distance_map_units,
        "outdoor_distance_m": geometry.outdoor_distance_m,
        "indoor_distance_m": geometry.indoor_distance_m,
        "blocking_building_ids": list(geometry.blocking_building_ids),
        "all_surface_crossings": [
            _surface_crossing_to_report(crossing)
            for crossing in geometry.all_surface_crossings
        ],
        "effective_surface_crossings": [
            _surface_crossing_to_report(crossing)
            for crossing in geometry.effective_surface_crossings
        ],
        "exterior_surfaces_crossed": [
            _surface_crossing_to_report(crossing)
            for crossing in geometry.exterior_surfaces_crossed
        ],
        "interior_walls_crossed": [
            _surface_crossing_to_report(crossing)
            for crossing in geometry.interior_walls_crossed
        ],
        "portals_crossed": [
            _portal_crossing_to_report(portal)
            for portal in geometry.portals_crossed
        ],
    }


def _link_distance(
    start: tuple[float, float],
    end: tuple[float, float],
    coordinate_view: CoordinateCalibrationView | None,
) -> LinkDistance:
    map_distance = _distance(start, end)
    distance_2d_m = _map_units_to_meters(map_distance, coordinate_view)
    distance_3d_m = None
    if (
        distance_2d_m is not None
        and coordinate_view is not None
        and coordinate_view.gnb_height_m is not None
        and coordinate_view.ue_height_m is not None
    ):
        height_delta = coordinate_view.gnb_height_m - coordinate_view.ue_height_m
        distance_3d_m = math.sqrt(distance_2d_m * distance_2d_m + height_delta * height_delta)
    return LinkDistance(
        map_distance_units=map_distance,
        distance_2d_m=distance_2d_m,
        distance_3d_m=distance_3d_m,
    )


def _normalize_wall_crossings(
    walls: list[dict],
    *,
    coordinate_view: CoordinateCalibrationView | None,
) -> list[PropagationSurfaceCrossing]:
    crossings: list[PropagationSurfaceCrossing] = []
    for index, wall in enumerate(walls):
        segment = wall.get("segment") or ((0.0, 0.0), (0.0, 0.0))
        start = _point_tuple(segment[0])
        end = _point_tuple(segment[1])
        intersection = _point_tuple(wall.get("intersection", start))
        distance_from_gnb = float(wall.get("distance_from_start") or 0.0)
        wall_id = wall.get("wall_id") or _stable_surface_id(wall, index)
        crossings.append(
            PropagationSurfaceCrossing(
                surface_id=str(wall_id),
                name=_optional_str(wall.get("name")),
                scope=str(wall.get("scope") or "unknown"),
                wall_type=_wall_type(wall),
                material=_optional_str(wall.get("material")),
                area_id=_optional_str(wall.get("area_id")),
                area_name=_optional_str(wall.get("area_name")),
                intersection=intersection,
                distance_from_gnb_map_units=distance_from_gnb,
                distance_from_gnb_m=_map_units_to_meters(distance_from_gnb, coordinate_view),
                penetration_loss_db=float(wall.get("penetration_loss_db") or 0.0),
                segment=(start, end),
            )
        )
    crossings.sort(key=lambda crossing: crossing.distance_from_gnb_map_units)
    return crossings


def _deduplicate_crossings(
    crossings: list[PropagationSurfaceCrossing],
    *,
    tolerance: float = INTERSECTION_TOLERANCE_MAP_UNITS,
) -> None:
    seen_surface_ids: set[str] = set()
    for crossing in crossings:
        if crossing.surface_id in seen_surface_ids:
            crossing.is_effective = False
            crossing.ignored_reason = IGNORED_DUPLICATE_SURFACE
            continue
        seen_surface_ids.add(crossing.surface_id)

    active = [crossing for crossing in crossings if crossing.is_effective]
    groups: list[list[PropagationSurfaceCrossing]] = []
    for crossing in active:
        for group in groups:
            if _same_crossing_location(crossing, group[0], tolerance=tolerance):
                group.append(crossing)
                break
        else:
            groups.append([crossing])

    for group in groups:
        if len(group) <= 1:
            continue
        preferred = max(group, key=_surface_priority)
        for crossing in group:
            if crossing is preferred:
                continue
            crossing.is_effective = False
            crossing.ignored_reason = IGNORED_DUPLICATE_SURFACE


def _portal_crossings(
    scene,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    coordinate_view: CoordinateCalibrationView | None,
) -> list[PortalCrossing]:
    crossings: list[PortalCrossing] = []
    for portal in _iter_global_portals(scene):
        if not _is_propagation_portal(portal):
            continue
        intersection = _segment_intersection(start, end, portal["segment"][0], portal["segment"][1])
        if intersection is None:
            continue
        distance_from_gnb = _distance(start, intersection)
        crossings.append(
            PortalCrossing(
                portal_id=str(portal["portal_id"]),
                name=_optional_str(portal.get("name")),
                kind=_optional_str(portal.get("kind")),
                role=_optional_str(portal.get("role")),
                open=bool(portal.get("open", True)),
                locked=bool(portal.get("locked", False)),
                wall_id=_optional_str(portal.get("wall_id")),
                areas=portal.get("areas"),
                segment=portal["segment"],
                intersection=intersection,
                distance_from_gnb_map_units=distance_from_gnb,
                distance_from_gnb_m=_map_units_to_meters(distance_from_gnb, coordinate_view),
            )
        )
    crossings.sort(key=lambda crossing: crossing.distance_from_gnb_map_units or 0.0)
    return crossings


def _apply_open_portals(
    crossings: list[PropagationSurfaceCrossing],
    portals_crossed: list[PortalCrossing],
    *,
    tolerance: float = INTERSECTION_TOLERANCE_MAP_UNITS,
) -> None:
    for portal in portals_crossed:
        if not portal.open:
            continue
        for crossing in crossings:
            if not crossing.is_effective:
                continue
            if _portal_matches_surface(portal, crossing, tolerance=tolerance):
                crossing.is_effective = False
                crossing.ignored_reason = IGNORED_OPEN_PORTAL


def _iter_global_portals(scene) -> list[dict]:
    portals: list[dict] = []
    for portal in getattr(scene, "portals", []):
        portals.append(_portal_summary(portal, parent_area=None))
    for area in getattr(scene, "areas", []):
        portals.extend(_iter_area_portals(area, parent_area=area))
    return portals


def _iter_area_portals(area, *, parent_area) -> list[dict]:
    portals: list[dict] = []
    for portal in getattr(area, "portals", []):
        portals.append(_portal_summary(portal, parent_area=parent_area))
    for child_area in getattr(area, "areas", []):
        portals.extend(_iter_area_portals(child_area, parent_area=parent_area))
    return portals


def _portal_summary(portal, *, parent_area) -> dict:
    portal_id = _field(portal, "portal_id") or _field(portal, "id") or "portal"
    segment = _field(portal, "segment") or ((0.0, 0.0), (0.0, 0.0))
    segment_points = (_point_tuple(segment[0]), _point_tuple(segment[1]))
    if parent_area is not None:
        segment_points = tuple(_local_point_to_global(point, parent_area) for point in segment_points)

    areas = _field(portal, "areas")
    if areas is not None:
        areas = tuple(str(area_id) for area_id in areas[:2])
    return {
        "portal_id": str(portal_id),
        "name": _field(portal, "name"),
        "kind": _field(portal, "kind"),
        "role": _field(portal, "role"),
        "locked": bool(_field(portal, "locked")),
        "wall_id": _field(portal, "wall_id"),
        "areas": areas,
        "segment": segment_points,
        "open": bool(_field(portal, "open") if _field(portal, "open") is not None else True),
    }


def _split_indoor_outdoor_distance(
    *,
    link_type: str,
    total_map_distance: float,
    gnb_area_id: str | None,
    receiver_building_id: str | None,
    effective_crossings: list[PropagationSurfaceCrossing],
    all_crossings: list[PropagationSurfaceCrossing],
) -> tuple[float, float]:
    if link_type in {LINK_OUTDOOR_LOS, LINK_OUTDOOR_NLOS}:
        return total_map_distance, 0.0
    if link_type == LINK_INDOOR_SAME_BUILDING:
        return 0.0, total_map_distance
    if link_type == LINK_OUTDOOR_TO_INDOOR:
        entry = _target_exterior_crossing(all_crossings, receiver_building_id, nearest_to_receiver=True)
        if entry is None:
            return 0.0, total_map_distance
        indoor = max(0.0, total_map_distance - entry.distance_from_gnb_map_units)
        return max(0.0, total_map_distance - indoor), indoor
    if link_type == LINK_INDOOR_TO_OUTDOOR:
        exit_crossing = _target_exterior_crossing(all_crossings, gnb_area_id, nearest_to_receiver=False)
        if exit_crossing is None:
            return 0.0, total_map_distance
        indoor = max(0.0, exit_crossing.distance_from_gnb_map_units)
        return max(0.0, total_map_distance - indoor), indoor
    if link_type == LINK_INDOOR_DIFFERENT_BUILDING:
        exterior = [crossing for crossing in effective_crossings if _is_exterior(crossing) is not None]
        exterior.sort(key=lambda crossing: crossing.distance_from_gnb_map_units)
        if len(exterior) >= 2:
            first = exterior[0].distance_from_gnb_map_units
            last = exterior[-1].distance_from_gnb_map_units
            indoor = max(0.0, first) + max(0.0, total_map_distance - last)
            return max(0.0, total_map_distance - indoor), indoor
        return 0.0, total_map_distance
    return total_map_distance, 0.0


def _target_exterior_crossing(
    crossings: list[PropagationSurfaceCrossing],
    building_id: str | None,
    *,
    nearest_to_receiver: bool,
) -> PropagationSurfaceCrossing | None:
    if building_id is None:
        return None
    candidates = [
        crossing
        for crossing in crossings
        if crossing.area_id == building_id and _is_exterior(crossing) is not None
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda crossing: crossing.distance_from_gnb_map_units)
    return candidates[-1] if nearest_to_receiver else candidates[0]


def _classify_link(
    *,
    gnb_space: str,
    receiver_space: str,
    gnb_area_id: str | None,
    receiver_area_id: str | None,
    effective_crossings: list[PropagationSurfaceCrossing],
) -> str:
    if gnb_space == "outdoor" and receiver_space == "outdoor":
        return LINK_OUTDOOR_NLOS if effective_crossings else LINK_OUTDOOR_LOS
    if gnb_space == "outdoor" and receiver_space == "indoor":
        return LINK_OUTDOOR_TO_INDOOR
    if gnb_space == "indoor" and receiver_space == "outdoor":
        return LINK_INDOOR_TO_OUTDOOR
    if gnb_space == "indoor" and receiver_space == "indoor":
        if gnb_area_id == receiver_area_id:
            return LINK_INDOOR_SAME_BUILDING
        return LINK_INDOOR_DIFFERENT_BUILDING
    return LINK_OUTDOOR_NLOS if effective_crossings else LINK_OUTDOOR_LOS


def _blocking_buildings(
    *,
    candidate_crossings: list[PropagationSurfaceCrossing],
    link_type: str,
    receiver_building_id: str | None,
    gnb_area_id: str | None,
) -> list[str]:
    target_area_ids = _target_area_ids_for_material_surfaces(
        link_type=link_type,
        gnb_area_id=gnb_area_id,
        receiver_building_id=receiver_building_id,
    )
    building_ids: list[str] = []
    for crossing in candidate_crossings:
        if _is_exterior(crossing) is None or crossing.area_id is None:
            continue
        if crossing.area_id in target_area_ids:
            continue
        if crossing.area_id not in building_ids:
            building_ids.append(crossing.area_id)
    return building_ids


def _apply_link_context_filter(
    *,
    link_type: str,
    gnb_area_id: str | None,
    receiver_building_id: str | None,
    crossings: list[PropagationSurfaceCrossing],
) -> None:
    target_area_ids = _target_area_ids_for_material_surfaces(
        link_type=link_type,
        gnb_area_id=gnb_area_id,
        receiver_building_id=receiver_building_id,
    )
    for crossing in crossings:
        if not crossing.is_effective:
            continue
        if crossing.area_id is None:
            continue
        if crossing.area_id in target_area_ids:
            continue
        crossing.is_effective = False
        crossing.ignored_reason = IGNORED_BLOCKING_BUILDING_NLOS


def _target_area_ids_for_material_surfaces(
    *,
    link_type: str,
    gnb_area_id: str | None,
    receiver_building_id: str | None,
) -> set[str]:
    if link_type == LINK_OUTDOOR_TO_INDOOR:
        return {receiver_building_id} if receiver_building_id else set()
    if link_type == LINK_INDOOR_TO_OUTDOOR:
        return {gnb_area_id} if gnb_area_id else set()
    if link_type == LINK_INDOOR_SAME_BUILDING:
        return {gnb_area_id} if gnb_area_id else set()
    if link_type == LINK_INDOOR_DIFFERENT_BUILDING:
        return {area_id for area_id in (gnb_area_id, receiver_building_id) if area_id}
    return set()


def _is_exterior(crossing: PropagationSurfaceCrossing) -> PropagationSurfaceCrossing | None:
    if crossing.wall_type == "exterior" or crossing.scope == "area_boundary":
        return crossing
    return None


def _is_interior(crossing: PropagationSurfaceCrossing) -> PropagationSurfaceCrossing | None:
    if crossing.wall_type == "interior":
        return crossing
    return None


def _portal_matches_surface(
    portal: PortalCrossing,
    crossing: PropagationSurfaceCrossing,
    *,
    tolerance: float,
) -> bool:
    if portal.wall_id and portal.wall_id == crossing.surface_id:
        return True
    if portal.intersection is not None:
        return _distance(portal.intersection, crossing.intersection) <= tolerance
    return False


def _is_propagation_portal(portal: dict) -> bool:
    kind = str(portal.get("kind") or "opening")
    if portal.get("wall_id"):
        return True
    return kind in {"building_entrance", "door", "open_passage", "opening"}


def _same_crossing_location(
    left: PropagationSurfaceCrossing,
    right: PropagationSurfaceCrossing,
    *,
    tolerance: float,
) -> bool:
    return (
        abs(left.distance_from_gnb_map_units - right.distance_from_gnb_map_units) <= tolerance
        and _distance(left.intersection, right.intersection) <= tolerance
    )


def _surface_priority(crossing: PropagationSurfaceCrossing) -> tuple[int, int, int]:
    explicit_score = 0 if crossing.scope == "area_boundary" else 1
    wall_type_score = 0 if crossing.wall_type in {None, "unknown"} else 1
    named_score = 1 if crossing.surface_id else 0
    return explicit_score, wall_type_score, named_score


def _surface_crossing_to_report(crossing: PropagationSurfaceCrossing) -> dict:
    return {
        "surface_id": crossing.surface_id,
        "name": crossing.name,
        "scope": crossing.scope,
        "wall_type": crossing.wall_type,
        "material": crossing.material,
        "area_id": crossing.area_id,
        "area_name": crossing.area_name,
        "intersection": list(crossing.intersection),
        "distance_from_gnb_map_units": crossing.distance_from_gnb_map_units,
        "distance_from_gnb_m": crossing.distance_from_gnb_m,
        "penetration_loss_db": crossing.penetration_loss_db,
        "segment": [list(crossing.segment[0]), list(crossing.segment[1])],
        "is_effective": crossing.is_effective,
        "ignored_reason": crossing.ignored_reason,
    }


def _portal_crossing_to_report(portal: PortalCrossing) -> dict:
    return {
        "portal_id": portal.portal_id,
        "name": portal.name,
        "kind": portal.kind,
        "role": portal.role,
        "open": portal.open,
        "locked": portal.locked,
        "wall_id": portal.wall_id,
        "areas": list(portal.areas) if portal.areas else None,
        "segment": [list(portal.segment[0]), list(portal.segment[1])],
        "intersection": list(portal.intersection) if portal.intersection else None,
        "distance_from_gnb_map_units": portal.distance_from_gnb_map_units,
        "distance_from_gnb_m": portal.distance_from_gnb_m,
    }


def _space(area_result: dict) -> str:
    return str(area_result.get("space") or "outdoor")


def _area_id(area_result: dict) -> str | None:
    area = area_result.get("area") or {}
    area_id = area.get("id")
    return str(area_id) if area_id else None


def _child_area_id(area_result: dict) -> str | None:
    child_area = area_result.get("child_area") or {}
    area_id = child_area.get("id")
    return str(area_id) if area_id else None


def _wall_type(wall: dict) -> str | None:
    wall_type = wall.get("wall_type")
    if wall_type:
        return str(wall_type)
    if wall.get("scope") == "area_boundary":
        return "exterior"
    return None


def _stable_surface_id(wall: dict, index: int) -> str:
    area_id = wall.get("area_id") or "scene"
    intersection = wall.get("intersection") or (0.0, 0.0)
    return f"{area_id}_surface_{index}_{float(intersection[0]):.3f}_{float(intersection[1]):.3f}"


def _map_units_to_meters(
    value: float,
    coordinate_view: CoordinateCalibrationView | None,
) -> float | None:
    if coordinate_view is None or coordinate_view.meters_per_map_unit is None:
        return None
    return value * coordinate_view.meters_per_map_unit


def _local_point_to_global(point: tuple[float, float], parent_area) -> tuple[float, float]:
    local_bounds = _area_local_bounds(parent_area)
    local_width = max(1.0, local_bounds[2] - local_bounds[0])
    local_height = max(1.0, local_bounds[3] - local_bounds[1])
    parent_width = parent_area.bounds[2] - parent_area.bounds[0]
    parent_height = parent_area.bounds[3] - parent_area.bounds[1]
    return (
        parent_area.bounds[0] + (point[0] - local_bounds[0]) * parent_width / local_width,
        parent_area.bounds[1] + (point[1] - local_bounds[1]) * parent_height / local_height,
    )


def _area_local_bounds(area) -> tuple[float, float, float, float]:
    bounds = area.rendering.get("map_bounds") if getattr(area, "rendering", None) else None
    if bounds:
        return tuple(float(value) for value in bounds)
    return (0.0, 0.0, area.bounds[2] - area.bounds[0], area.bounds[3] - area.bounds[1])


def _segment_intersection(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
    d: tuple[float, float],
) -> tuple[float, float] | None:
    ax, ay = a
    bx, by = b
    cx, cy = c
    dx, dy = d
    r = (bx - ax, by - ay)
    s = (dx - cx, dy - cy)
    denominator = _cross(r, s)
    q_minus_p = (cx - ax, cy - ay)

    if abs(denominator) < 1e-9:
        if abs(_cross(q_minus_p, r)) >= 1e-9:
            return None
        return _collinear_overlap_point(a, b, c, d)

    t = _cross(q_minus_p, s) / denominator
    u = _cross(q_minus_p, r) / denominator
    if -1e-9 <= t <= 1 + 1e-9 and -1e-9 <= u <= 1 + 1e-9:
        return (ax + t * r[0], ay + t * r[1])
    return None


def _collinear_overlap_point(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
    d: tuple[float, float],
) -> tuple[float, float] | None:
    ab = (b[0] - a[0], b[1] - a[1])
    length_sq = ab[0] * ab[0] + ab[1] * ab[1]
    if length_sq < 1e-9:
        return a if _point_on_segment(a, c, d) else None
    t1 = ((c[0] - a[0]) * ab[0] + (c[1] - a[1]) * ab[1]) / length_sq
    t2 = ((d[0] - a[0]) * ab[0] + (d[1] - a[1]) * ab[1]) / length_sq
    start_t = max(0.0, min(t1, t2))
    end_t = min(1.0, max(t1, t2))
    if start_t <= end_t + 1e-9:
        return (a[0] + start_t * ab[0], a[1] + start_t * ab[1])
    return None


def _point_on_segment(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> bool:
    return (
        min(start[0], end[0]) - 1e-9 <= point[0] <= max(start[0], end[0]) + 1e-9
        and min(start[1], end[1]) - 1e-9 <= point[1] <= max(start[1], end[1]) + 1e-9
    )


def _cross(a: tuple[float, float], b: tuple[float, float]) -> float:
    return a[0] * b[1] - a[1] * b[0]


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5


def _point_tuple(value) -> tuple[float, float]:
    return (float(value[0]), float(value[1]))


def _optional_str(value) -> str | None:
    if value is None:
        return None
    return str(value)


def _field(item: Any, field_name: str):
    if isinstance(item, dict):
        return item.get(field_name)
    if is_dataclass(item):
        return asdict(item).get(field_name)
    return getattr(item, field_name, None)
