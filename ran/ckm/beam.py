"""Codebook-based Beamforming (phase 8): pattern, codebook, LOS/NLOS constraints, beam selection.

3GPP-style simplified horizontal pattern (doc 12.4):
  attenuation_db = min(12 × (relative_angle / beamwidth_3db)², max_attenuation_db)
  beam_gain_db   = max_gain_dbi - attenuation_db
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass(slots=True)
class BeamConfig:
    beam_id: str
    azimuth_deg: float
    beamwidth_deg: float
    max_gain_dbi: float
    side_lobe_level_db: float = 25.0


@dataclass(slots=True)
class BeamSelection:
    beam_id: str
    beam_azimuth_deg: float
    geometric_azimuth_deg: float
    relative_angle_deg: float
    beam_gain_db: float
    effective_received_power_dbm: float
    second_best_beam_id: str
    beam_margin_db: float


def beam_gain_db(beam: BeamConfig, relative_angle_deg: float) -> float:
    """Horizontal-pattern gain (relative_angle ∈ [-180, 180])."""

    angle = abs(((relative_angle_deg + 180.0) % 360.0) - 180.0)
    if beam.beamwidth_deg <= 0:
        return beam.max_gain_dbi
    attenuation = 12.0 * (angle / beam.beamwidth_deg) ** 2
    attenuation = min(attenuation, beam.side_lobe_level_db)
    return beam.max_gain_dbi - attenuation


def select_best_beam(
    *,
    gnb,
    ue_x: float,
    ue_y: float,
    los_state: str,
    codebook: list[BeamConfig],
    nlos_gain_cap_db: float | None = None,
    tx_power_dbm: float,
    path_loss_db: float,
) -> BeamSelection | None:
    """Scan the codebook and select the best beam (by effective received power). LOS gets full gain; NLOS is capped by a gain limit."""

    if not codebook:
        return None
    geometric_azimuth = math.degrees(math.atan2(ue_y - gnb.position.y, ue_x - gnb.position.x))
    candidates = []
    for beam in codebook:
        relative = ((geometric_azimuth - beam.azimuth_deg + 180.0) % 360.0) - 180.0
        gain = beam_gain_db(beam, relative)
        if los_state == "nlos" and nlos_gain_cap_db is not None:
            gain = min(gain, nlos_gain_cap_db)
        received = tx_power_dbm + gain - path_loss_db
        candidates.append((received, beam, relative, gain))
    candidates.sort(key=lambda item: item[0], reverse=True)
    best = candidates[0]
    second = candidates[1] if len(candidates) > 1 else candidates[0]
    return BeamSelection(
        beam_id=best[1].beam_id,
        beam_azimuth_deg=best[1].azimuth_deg,
        geometric_azimuth_deg=geometric_azimuth,
        relative_angle_deg=best[2],
        beam_gain_db=best[3],
        effective_received_power_dbm=best[0],
        second_best_beam_id=second[1].beam_id,
        beam_margin_db=best[0] - second[0],
    )


def default_codebook() -> list[BeamConfig]:
    """Default 8-beam codebook (0°/45°/.../315°, 45° beamwidth, 12 dBi peak)."""

    return [
        BeamConfig(beam_id=f"b{i}", azimuth_deg=float(i * 45), beamwidth_deg=45.0, max_gain_dbi=12.0)
        for i in range(8)
    ]
