from __future__ import annotations

import math

from ran.contracts import ChannelState, GnbSite, Position, UERequest
from ran.radio.channel_pipeline import evaluate_channel_path_loss
from ran.radio.channel_policy import load_channel_model_policy
from services.map_service import MapService


def estimate_channel(*, tick: int, scene, ue_request: UERequest, gnb: GnbSite) -> ChannelState:
    """Project implementation detail."""

    map_service = MapService()
    ue_pos = ue_request.position
    distance = _distance(ue_pos, gnb.position)
    area_result = map_service.get_area_at(scene, ue_pos.x, ue_pos.y)
    walls_result = map_service.get_walls_between(
        scene,
        (ue_pos.x, ue_pos.y),
        (gnb.position.x, gnb.position.y),
    )
    walls = walls_result.get("walls", [])
    wall_loss = sum(float(wall.get("penetration_loss_db") or 0.0) for wall in walls)

    d = max(distance, 1.0)
    legacy_path_loss = (
        32.4
        + 20.0 * math.log10(gnb.carrier_freq_mhz)
        + 20.0 * math.log10(d / 1000.0)
        + wall_loss
    )
    scene_id = str(getattr(scene, "node_id", ""))
    policy = load_channel_model_policy(scene_id)
    path_loss_evaluation = evaluate_channel_path_loss(
        scene=scene,
        receiver_position=ue_pos,
        gnb=gnb,
        legacy_total_path_loss_db=legacy_path_loss,
        policy=policy,
    )
    path_loss = path_loss_evaluation.selected_total_path_loss_db
    antenna_gain = min(12.0, 10.0 * math.log10(max(1, gnb.antenna_elements)) * 0.5)
    received_power = gnb.tx_power_dbm + antenna_gain - path_loss
    noise_floor = -94.0
    sinr = received_power - noise_floor
    cqi = _sinr_to_cqi(sinr)
    per = _cqi_to_error_rate(cqi)

    geometry = path_loss_evaluation.geometry
    return ChannelState(
        tick=tick,
        ue_id=ue_request.ue_id,
        gnb_id=gnb.gnb_id,
        direction=ue_request.direction,
        distance_m=distance,
        ue_area_id=(area_result.get("child_area") or area_result.get("area") or {}).get("id"),
        ue_space_type=str(area_result.get("space") or "outdoor"),
        walls_crossed=[str(wall.get("wall_id")) for wall in walls],
        wall_loss_db=wall_loss,
        total_path_loss_db=path_loss,
        received_power_dbm=received_power,
        sinr_db=sinr,
        cqi=cqi,
        estimated_packet_error_rate=per,
        channel_model_mode=path_loss_evaluation.mode,
        path_loss_model=path_loss_evaluation.selected_model,
        path_loss_formula_id=path_loss_evaluation.selected_formula_id,
        evaluated_path_loss_model=path_loss_evaluation.evaluated_model,
        evaluated_total_path_loss_db=(
            path_loss_evaluation.evaluated_total_path_loss_db
        ),
        evaluated_formula_id=path_loss_evaluation.evaluated_formula_id,
        link_type=geometry.link_type if geometry is not None else "unknown",
        los_state=geometry.los_state if geometry is not None else "unknown",
        map_distance_units=(
            geometry.distance.map_distance_units if geometry is not None else None
        ),
        distance_2d_m=(
            geometry.distance.distance_2d_m if geometry is not None else None
        ),
        distance_3d_m=(
            geometry.distance.distance_3d_m if geometry is not None else None
        ),
        outdoor_distance_m=(geometry.outdoor_distance_m if geometry is not None else None),
        indoor_distance_m=(geometry.indoor_distance_m if geometry is not None else None),
        effective_walls_crossed=(
            [item.surface_id for item in geometry.effective_surface_crossings]
            if geometry is not None
            else []
        ),
        portals_crossed=(
            [item.portal_id for item in geometry.portals_crossed]
            if geometry is not None
            else []
        ),
        external_wall_loss_db=path_loss_evaluation.external_wall_loss_db,
        indoor_loss_db=path_loss_evaluation.indoor_loss_db,
        shadow_fading_std_db=path_loss_evaluation.shadow_fading_std_db,
        penetration_loss_std_db=path_loss_evaluation.penetration_loss_std_db,
        is_extrapolated=path_loss_evaluation.is_extrapolated,
        path_loss_warnings=list(path_loss_evaluation.warnings),
        fallback_reason=path_loss_evaluation.fallback_reason,
        calibration_id=path_loss_evaluation.calibration_id,
        calibration_status=path_loss_evaluation.calibration_status,
        meters_per_map_unit_x=path_loss_evaluation.meters_per_map_unit_x,
        meters_per_map_unit_y=path_loss_evaluation.meters_per_map_unit_y,
        bs_height_m=path_loss_evaluation.bs_height_m,
        bs_height_source=path_loss_evaluation.bs_height_source,
        bs_height_status=path_loss_evaluation.bs_height_status,
        ut_height_m=path_loss_evaluation.ut_height_m,
        ut_height_source=path_loss_evaluation.ut_height_source,
        ut_height_status=path_loss_evaluation.ut_height_status,
        height_reference=path_loss_evaluation.height_reference,
        penetration_model=path_loss_evaluation.penetration_model,
        penetration_model_source=path_loss_evaluation.penetration_model_source,
        penetration_model_status=path_loss_evaluation.penetration_model_status,
    )


def _distance(a: Position, b: Position) -> float:
    return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5


def _sinr_to_cqi(sinr_db: float) -> int:
    return max(1, min(15, int((sinr_db + 8.0) // 2.0)))


def _cqi_to_error_rate(cqi: int) -> float:
    return max(0.001, min(0.5, 0.30 * math.exp(-0.23 * cqi)))
