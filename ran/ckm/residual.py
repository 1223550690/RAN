"""空间残差模型(环节六):IDW 插值 + 距离衰减方差(零依赖首版)。

residual_i = measured_pl_i - calibrated_physical_pl_i
residual_mean(x) = Σ w_i·r_i / Σ w_i          w_i = 1/d(x,x_i)²
residual_std(x)  = 加权样本方差 + (d_min/d_ref)²·σ_prior²(未测区域不确定性增长)
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(slots=True)
class ResidualPrediction:
    residual_mean_db: float
    residual_std_db: float
    nearest_measurement_distance_m: float
    supporting_measurement_count: int


@dataclass(slots=True)
class ResidualPoint:
    x_map: float
    y_map: float
    residual_db: float


class IdwResidualModel:
    """IDW 空间残差:参考点少时回退纯物理先验(mean=0, std=prior)。"""

    def __init__(
        self,
        points: list[ResidualPoint],
        *,
        power: float = 2.0,
        max_neighbors: int = 8,
        prior_std_db: float = 6.0,
        reference_distance_m: float = 50.0,
    ) -> None:
        self.points = points
        self.power = power
        self.max_neighbors = max_neighbors
        self.prior_std_db = prior_std_db
        self.reference_distance_m = reference_distance_m

    def predict(self, x_map: float, y_map: float) -> ResidualPrediction:
        if not self.points:
            return ResidualPrediction(0.0, self.prior_std_db, float("inf"), 0)
        # 按距离排序取近邻
        scored = sorted(
            ((p, math.hypot(p.x_map - x_map, p.y_map - y_map)) for p in self.points),
            key=lambda item: item[1],
        )
        neighbors = scored[: self.max_neighbors]
        nearest_d = neighbors[0][1]
        d_min = max(nearest_d, 1e-6)
        weights = [1.0 / (d**self.power) if d > 1e-6 else 1e6 for _, d in neighbors]
        total_w = sum(weights)
        mean = sum(w * p.residual_db for (p, _), w in zip(neighbors, weights)) / total_w
        variance = sum(w * (p.residual_db - mean) ** 2 for (p, _), w in zip(neighbors, weights)) / total_w
        uncertainty = (d_min / max(self.reference_distance_m, 1e-6)) ** 2 * (self.prior_std_db**2)
        return ResidualPrediction(
            residual_mean_db=mean,
            residual_std_db=math.sqrt(variance + uncertainty),
            nearest_measurement_distance_m=d_min,
            supporting_measurement_count=len(neighbors),
        )
