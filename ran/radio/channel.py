from __future__ import annotations

import math

from ran.contracts import ChannelState, GnbSite, Position, UERequest
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
    path_loss = 32.4 + 20.0 * math.log10(gnb.carrier_freq_mhz) + 20.0 * math.log10(d / 1000.0) + wall_loss
    antenna_gain = min(12.0, 10.0 * math.log10(max(1, gnb.antenna_elements)) * 0.5)
    received_power = gnb.tx_power_dbm + antenna_gain - path_loss
    noise_floor = -94.0
    sinr = received_power - noise_floor
    cqi = _sinr_to_cqi(sinr)
    per = _cqi_to_error_rate(cqi)

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
    )


def _distance(a: Position, b: Position) -> float:
    return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5


def _sinr_to_cqi(sinr_db: float) -> int:
    return max(1, min(15, int((sinr_db + 8.0) // 2.0)))


def _cqi_to_error_rate(cqi: int) -> float:
    return max(0.001, min(0.5, 0.30 * math.exp(-0.23 * cqi)))
