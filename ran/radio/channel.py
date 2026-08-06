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
    hybrid_state = _estimate_hybrid_channel(
        tick=tick,
        scene=scene,
        ue_request=ue_request,
        gnb=gnb,
        policy=policy,
        distance=distance,
    )
    if hybrid_state is not None:
        return hybrid_state
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
    noise_floor = _noise_floor_db(gnb, policy)
    sinr = received_power - noise_floor
    cqi = _sinr_to_cqi(sinr)
    per = _sinr_to_bler(sinr, cqi)

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


def _estimate_hybrid_channel(
    *,
    tick: int,
    scene,
    ue_request: UERequest,
    gnb: GnbSite,
    policy,
    distance: float,
) -> ChannelState | None:
    """Hybrid mode: CKM query + beam selection.

    Returns None when the CKM is unavailable (mode disabled / not built /
    query failed); the caller falls back.
    """

    if not getattr(policy, "is_hybrid", False):
        return None
    ckm = getattr(scene, "ckm", None)
    if ckm is None:
        return None
    cell = ckm.query(ue_request.position.x, ue_request.position.y)
    if cell is None:
        return None

    # Beam selection (real-time azimuth; NLOS is capped by a gain limit)
    beam_gain = 0.0
    beam_id = None
    beam_azimuth = None
    margin = None
    ckm_config = getattr(policy, "ckm_config", None) or {}
    beam_cfg = ckm_config.get("beam") or {}
    if beam_cfg.get("enabled", True):
        try:
            from ran.ckm.beam import BeamConfig, default_codebook, select_best_beam

            raw_codebook = beam_cfg.get("codebook") or []
            if raw_codebook:
                codebook = [
                    BeamConfig(
                        beam_id=str(b.get("beam_id")),
                        azimuth_deg=float(b.get("azimuth_deg", 0.0)),
                        beamwidth_deg=float(b.get("beamwidth_deg", 45.0)),
                        max_gain_dbi=float(b.get("max_gain_dbi", 12.0)),
                        side_lobe_level_db=float(b.get("side_lobe_level_db", 25.0)),
                    )
                    for b in raw_codebook
                ]
            else:
                codebook = default_codebook()
            nlos_cap = float(beam_cfg["nlos_gain_cap_db"]) if beam_cfg.get("nlos_gain_cap_db") is not None else -3.0
            selection = select_best_beam(
                gnb=gnb,
                ue_x=ue_request.position.x,
                ue_y=ue_request.position.y,
                los_state=cell.los_state,
                codebook=codebook,
                nlos_gain_cap_db=nlos_cap,
                tx_power_dbm=gnb.tx_power_dbm,
                path_loss_db=cell.hybrid_path_loss_db,
            )
            if selection is not None:
                beam_gain = selection.beam_gain_db
                beam_id = selection.beam_id
                beam_azimuth = selection.beam_azimuth_deg
                margin = selection.beam_margin_db
        except Exception:
            beam_gain = 0.0

    received_power = gnb.tx_power_dbm + beam_gain - cell.hybrid_path_loss_db
    noise_floor = _noise_floor_db(gnb, policy)
    sinr = received_power - noise_floor
    cqi = _sinr_to_cqi(sinr)
    per = _sinr_to_bler(sinr, cqi)

    return ChannelState(
        tick=tick,
        ue_id=ue_request.ue_id,
        gnb_id=gnb.gnb_id,
        direction=ue_request.direction,
        distance_m=distance,
        ue_area_id=cell.receiver_building_id,
        ue_space_type=cell.receiver_space,
        walls_crossed=list(cell.exterior_walls_crossed) + list(cell.interior_walls_crossed),
        wall_loss_db=0.0,
        total_path_loss_db=cell.hybrid_path_loss_db,
        received_power_dbm=received_power,
        sinr_db=sinr,
        cqi=cqi,
        estimated_packet_error_rate=per,
        channel_model_mode="hybrid",
        path_loss_model="hybrid_ckm",
        path_loss_formula_id="hybrid_physical_calibrated_residual",
        evaluated_path_loss_model="hybrid_ckm",
        evaluated_total_path_loss_db=cell.hybrid_path_loss_db,
        evaluated_formula_id="hybrid_ckm",
        link_type=cell.link_type,
        los_state=cell.los_state,
        map_distance_units=distance,
        distance_2d_m=cell.distance_2d_m,
        distance_3d_m=cell.distance_3d_m,
        outdoor_distance_m=cell.outdoor_distance_m,
        indoor_distance_m=cell.indoor_distance_m,
        effective_walls_crossed=list(cell.exterior_walls_crossed) + list(cell.interior_walls_crossed),
        portals_crossed=list(cell.portals_crossed),
        shadow_fading_std_db=cell.shadow_std_db,
        prediction_std_db=cell.prediction_std_db,
        beam_id=beam_id,
        beam_gain_db=beam_gain,
        beam_azimuth_deg=beam_azimuth,
        beam_margin_db=margin,
        is_extrapolated=False,
        calibration_id="hybrid_ckm",
        calibration_status="confirmed",
    )


def _noise_floor_db(gnb, policy) -> float:
    """Thermal noise floor (phase 10, doc 14.1): -174 + 10*log10(BW) + NF.

    Default 20 MHz + NF 7 dB ≈ -94 dBm (same order as the original fixed
    value; automatically follows bandwidth/NF changes).
    """

    bandwidth_hz = max(getattr(gnb, "bandwidth_mhz", 20.0), 0.1) * 1e6
    noise_figure = float(getattr(policy, "noise_figure_db", 7.0) or 7.0)
    return -174.0 + 10.0 * math.log10(bandwidth_hz) + noise_figure


def _sinr_to_cqi(sinr_db: float) -> int:
    """SINR → CQI: standard table lookup (TS 38.214 operating point, doc 15.3)."""

    from ran.radio.mcs_tables import sinr_to_cqi

    return sinr_to_cqi(sinr_db)


def _cqi_to_error_rate(cqi: int) -> float:
    """CQI → predicted BLER (standard operating point + sigmoid approximation)."""

    from ran.radio.mcs_tables import MAX_CQI, SINR_CQI_THRESHOLDS_DB

    cqi = max(1, min(MAX_CQI, int(cqi)))
    # Approximate via the working-point SINR=0 offset (compat with the old
    # interface; channel.py uses _sinr_to_bler for higher precision)
    working = SINR_CQI_THRESHOLDS_DB[cqi - 1]
    return max(0.001, min(0.5, 0.1 * math.exp(-1.2 * (0.0 - working))))


def _sinr_to_bler(sinr_db: float, cqi: int) -> float:
    """SINR + CQI → predicted BLER (doc 15.4: sigmoid near the 10% operating point)."""

    from ran.radio.mcs_tables import sinr_to_bler

    return sinr_to_bler(sinr_db, cqi)
