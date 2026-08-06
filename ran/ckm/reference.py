"""Reference samples: ChannelMeasurement + stratified sampling generator (phase 4).

Fallback when no real measurements exist: generate synthetic reference samples
with a high-fidelity model (3GPP + an independent shadow implementation) (doc
8.4: they can only be called reference samples, not claimed as measured
calibration). Stratified coverage: outdoor LOS/NLOS, shallow/deep O2I, indoor
single/multi-wall.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from ran.radio.geometry import PropagationGeometry, analyze_propagation_geometry
from ran.radio.channel_pipeline import evaluate_channel_path_loss


@dataclass(slots=True)
class ChannelMeasurement:
    """A single reference measurement point (large-scale, averaged over fast fading)."""

    measurement_id: str
    receiver_x_map: float
    receiver_y_map: float
    link_type: str
    los_state: str
    distance_3d_m: float
    indoor_distance_m: float
    exterior_wall_count: int
    interior_wall_count: int
    brick_wall_count: int
    glass_wall_count: int
    drywall_wall_count: int
    physical_path_loss_db: float  # physical prior (3GPP) prediction
    measured_path_loss_db: float  # reference observation (= physical + independent shadow implementation)
    measured_rsrp_dbm: float
    source: str = "synthetic"


def _material_counts(geometry: PropagationGeometry) -> tuple[int, int, int]:
    brick = glass = drywall = 0
    for crossing in geometry.effective_surface_crossings:
        material = str(getattr(crossing, "material", "") or "").lower()
        if material == "brick":
            brick += 1
        elif material == "glass":
            glass += 1
        elif material == "drywall":
            drywall += 1
    return brick, glass, drywall


def layer_of(geometry: PropagationGeometry) -> str:
    """Stratification key for reference sampling (doc 8.3)."""

    link = geometry.link_type
    if link == "outdoor_los":
        return "outdoor_los"
    if link == "outdoor_nlos":
        return "outdoor_nlos"
    indoor_m = geometry.indoor_distance_m or 0.0
    if link == "outdoor_to_indoor":
        return "o2i_shallow" if indoor_m < 10.0 else "o2i_deep"
    interior = len(geometry.interior_walls_crossed)
    if interior <= 1:
        return "indoor_single_wall"
    return "indoor_multi_wall"


def build_reference_measurements(
    *,
    scene,
    gnb,
    policy,
    candidate_points: list[dict],
    count: int,
    seed: int = 42,
    tx_power_dbm: float | None = None,
) -> list[ChannelMeasurement]:
    """Stratified-sample count points from the candidate grid points to generate
    synthetic references.

    candidate_points: [{"x": map_x, "y": map_y, "geometry": PropagationGeometry,
                        "path_loss_db": float, "shadow_std_db": float}, ...]
    """

    if count <= 0 or not candidate_points:
        return []
    rng = random.Random(seed)
    by_layer: dict[str, list[dict]] = {}
    for point in candidate_points:
        by_layer.setdefault(layer_of(point["geometry"]), []).append(point)

    layers = sorted(by_layer.keys())
    measurements: list[ChannelMeasurement] = []
    tx = tx_power_dbm if tx_power_dbm is not None else gnb.tx_power_dbm
    antenna_gain = min(12.0, 10.0 * math.log10(max(1, gnb.antenna_elements)) * 0.5)
    per_layer = max(1, count // max(1, len(layers)))
    index = 0
    for layer in layers:
        pool = by_layer[layer]
        picked = rng.sample(pool, min(per_layer, len(pool)))
        for point in picked:
            geometry: PropagationGeometry = point["geometry"]
            pl_db = float(point["path_loss_db"])
            shadow_std = float(point.get("shadow_std_db") or 0.0)
            shadow_impl = rng.gauss(0.0, shadow_std) if shadow_std > 0 else 0.0
            measured_pl = pl_db + shadow_impl
            brick, glass, drywall = _material_counts(geometry)
            measurements.append(
                ChannelMeasurement(
                    measurement_id=f"ref_{index:04d}",
                    receiver_x_map=point["x"],
                    receiver_y_map=point["y"],
                    link_type=geometry.link_type,
                    los_state=geometry.los_state,
                    distance_3d_m=geometry.distance.distance_3d_m or 0.0,
                    indoor_distance_m=geometry.indoor_distance_m or 0.0,
                    exterior_wall_count=len(geometry.exterior_surfaces_crossed),
                    interior_wall_count=len(geometry.interior_walls_crossed),
                    brick_wall_count=brick,
                    glass_wall_count=glass,
                    drywall_wall_count=drywall,
                    physical_path_loss_db=pl_db,
                    measured_path_loss_db=measured_pl,
                    measured_rsrp_dbm=tx + antenna_gain - measured_pl,
                )
            )
            index += 1
    return measurements
