"""Hybrid CKM (phase 7): grid cells, two-layer grid (fine indoor / coarse outdoor), O(1) query, cache and version key."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ran.radio.geometry import PropagationGeometry

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CKM_CACHE_DIR = PROJECT_ROOT / "outputs"


@dataclass(slots=True)
class HybridCKMCell:
    """Large-scale channel knowledge for a single grid cell (condensed from doc 11.3)."""

    grid_x: int
    grid_y: int
    x_map: float
    y_map: float
    receiver_space: str  # indoor / outdoor
    receiver_building_id: str | None
    link_type: str
    los_state: str
    distance_2d_m: float
    distance_3d_m: float
    outdoor_distance_m: float
    indoor_distance_m: float
    exterior_walls_crossed: list[str]
    interior_walls_crossed: list[str]
    portals_crossed: list[str]
    physical_path_loss_db: float  # 3GPP physical prior
    calibrated_path_loss_db: float  # + calibration correction
    residual_correction_db: float  # + spatial residual
    hybrid_path_loss_db: float  # final
    predicted_rsrp_dbm: float
    prediction_std_db: float
    best_beam_id: str | None
    best_beam_rsrp_dbm: float | None
    beam_margin_db: float | None
    shadow_std_db: float


@dataclass(slots=True)
class HybridCkm:
    """Hybrid CKM: two-layer grid (fine indoor, coarse outdoor) + query."""

    scene_id: str
    version_key: str
    grid_scale_m: float
    indoor_refine_scale_m: float
    cells: list[HybridCKMCell]
    model_metadata: dict = field(default_factory=dict)
    _indoor_cells: dict[tuple[int, int], HybridCKMCell] = field(default_factory=dict)
    _outdoor_cells: dict[tuple[int, int], HybridCKMCell] = field(default_factory=dict)
    _building_bounds: list[tuple[float, float, float, float]] = field(default_factory=list)

    def __post_init__(self) -> None:
        for cell in self.cells:
            key = (round(cell.x_map / self.indoor_refine_scale_m), round(cell.y_map / self.indoor_refine_scale_m))
            if cell.receiver_space == "indoor":
                self._indoor_cells[key] = cell
            else:
                self._outdoor_cells[key] = cell

    def query(self, x_map: float, y_map: float) -> HybridCKMCell | None:
        """Nearest grid cell query (O(1)); indoor hits the fine grid, outdoor the coarse grid."""

        # First check if inside a building (coarse lookup); half-open interval
        # consistent with sampling (boundary points count as outdoor, avoiding holes)
        in_building = False
        for bx0, by0, bx1, by1 in self._building_bounds:
            if bx0 <= x_map < bx1 and by0 <= y_map < by1:
                in_building = True
                break
        key = (
            round(x_map / (self.indoor_refine_scale_m if in_building else self.grid_scale_m)),
            round(y_map / (self.indoor_refine_scale_m if in_building else self.grid_scale_m)),
        )
        table = self._indoor_cells if in_building else self._outdoor_cells
        cell = table.get(key)
        if cell is not None:
            return cell
        # Fallback: the other table / nearest-neighbor scan (rare boundary points)
        fallback = self._outdoor_cells if in_building else self._indoor_cells
        cell = fallback.get(key)
        if cell is not None:
            return cell
        return self._nearest(x_map, y_map)

    def _nearest(self, x_map: float, y_map: float) -> HybridCKMCell | None:
        best = None
        best_d = float("inf")
        for table in (self._indoor_cells, self._outdoor_cells):
            for key, cell in table.items():
                d = math.hypot(cell.x_map - x_map, cell.y_map - y_map)
                if d < best_d:
                    best_d = d
                    best = cell
        return best

    # ------------------------------------------------------------ cache

    def to_json(self) -> dict:
        return {
            "scene_id": self.scene_id,
            "version_key": self.version_key,
            "grid_scale_m": self.grid_scale_m,
            "indoor_refine_scale_m": self.indoor_refine_scale_m,
            "building_bounds": self._building_bounds,
            "model_metadata": self.model_metadata,
            "cells": [asdict(cell) for cell in self.cells],
        }

    @staticmethod
    def from_json(data: dict) -> "HybridCkm":
        ckm = HybridCkm(
            scene_id=str(data["scene_id"]),
            version_key=str(data["version_key"]),
            grid_scale_m=float(data["grid_scale_m"]),
            indoor_refine_scale_m=float(data["indoor_refine_scale_m"]),
            cells=[HybridCKMCell(**item) for item in data["cells"]],
            model_metadata=dict(data.get("model_metadata") or {}),
        )
        ckm._building_bounds = [tuple(b) for b in data.get("building_bounds", [])]
        return ckm


def cache_path(scene_id: str) -> Path:
    return CKM_CACHE_DIR / f"ckm_cache_{scene_id}.json"


def compute_version_key(
    *,
    scene_id: str,
    gnb,
    calibration_version: str,
    reference_count: int,
    seed: int,
    policy_hash: str = "",
    scene_hash: str = "",
) -> str:
    """Version key: any change in scene structure / gNB / calibration / reference /
    codebook / channel policy (incl. O2I profiles) → rebuild.

    scene_hash: structural hash of wall/door geometry (the CKM auto-invalidates
    when the editor changes walls/doors, doc 11.4).
    """

    scene_repr = f"{scene_id}:{gnb.gnb_id}:{gnb.position.x:.1f}:{gnb.position.y:.1f}:{gnb.carrier_freq_mhz}:{gnb.tx_power_dbm}"
    raw = f"{scene_repr}|{calibration_version}|ref{reference_count}|seed{seed}|policy:{policy_hash}|scene:{scene_hash}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def scene_structure_hash(scene) -> str:
    """Stable structural hash of wall/door geometry (segment values of walls/portals).

    Traversal order and numeric representation are stable; unaffected by
    rendering-field/name changes.
    """

    parts: list[str] = []

    def walk(node) -> None:
        for wall in getattr(node, "walls", []) or []:
            start = getattr(wall, "start", None)
            end = getattr(wall, "end", None)
            if start is not None and end is not None:
                parts.append("w" + repr((start, end)))
        for portal in getattr(node, "portals", []) or []:
            seg = getattr(portal, "segment", None)
            if seg is not None:
                parts.append("p" + repr(seg))
        for child in getattr(node, "areas", []) or []:
            walk(child)

    walk(scene)
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]
