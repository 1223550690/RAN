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


def _cholesky(a: list[list[float]]) -> list[list[float]]:
    """零依赖 Cholesky 分解(下三角)。"""

    n = len(a)
    lower = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = a[i][j] - sum(lower[i][k] * lower[j][k] for k in range(j))
            if i == j:
                lower[i][j] = math.sqrt(s) if s > 1e-12 else 1e-6
            else:
                lower[i][j] = s / lower[j][j]
    return lower


def _solve_cholesky(lower: list[list[float]], b: list[float]) -> list[float]:
    """L·Lᵀ x = b 求解(前代 + 回代)。"""

    n = len(lower)
    y = [0.0] * n
    for i in range(n):
        y[i] = (b[i] - sum(lower[i][k] * y[k] for k in range(i))) / lower[i][i]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = (y[i] - sum(lower[k][i] * x[k] for k in range(i + 1, n))) / lower[i][i]
    return x


class GaussianProcessResidualModel:
    """GP(Kriging)空间残差(文档 10.2 推荐):Matérn 3/2 核 + 固定超参。

    零依赖(手写 Cholesky,样本 ≤80);预测方差反映未测区域不确定性,
    比 IDW 更正规(协方差结构由核函数刻画)。
    """

    def __init__(
        self,
        points: list[ResidualPoint],
        *,
        length_scale_m: float = 50.0,
        signal_std_db: float = 6.0,
        noise_std_db: float = 1.0,
        prior_std_db: float = 6.0,
    ) -> None:
        self.points = points
        self.length_scale_m = max(length_scale_m, 1e-3)
        self.signal_std_db = signal_std_db
        self.noise_std_db = noise_std_db
        self.prior_std_db = prior_std_db
        self._build()

    def _kernel(self, d: float) -> float:
        r = d / self.length_scale_m
        return self.signal_std_db**2 * (1.0 + math.sqrt(3.0) * r) * math.exp(-math.sqrt(3.0) * r)

    def _build(self) -> None:
        n = len(self.points)
        if n == 0:
            self._lower = []
            self._alpha = []
            self._kinv = []
            return
        k = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                d = math.hypot(
                    self.points[i].x_map - self.points[j].x_map,
                    self.points[i].y_map - self.points[j].y_map,
                )
                k[i][j] = self._kernel(d) + (self.noise_std_db**2 if i == j else 0.0)
        self._lower = _cholesky(k)
        y = [p.residual_db for p in self.points]
        self._alpha = _solve_cholesky(self._lower, y)
        # K⁻¹ 列(用于预测方差)
        self._kinv = [
            _solve_cholesky(self._lower, [1.0 if i == j else 0.0 for j in range(n)])
            for i in range(n)
        ]

    def predict(self, x_map: float, y_map: float) -> ResidualPrediction:
        if not self.points:
            return ResidualPrediction(0.0, self.prior_std_db, float("inf"), 0)
        n = len(self.points)
        k_star = [
            self._kernel(
                math.hypot(p.x_map - x_map, p.y_map - y_map)
            )
            for p in self.points
        ]
        mean = sum(k_star[i] * self._alpha[i] for i in range(n))
        var = self._kernel(0.0) - sum(
            k_star[i] * sum(self._kinv[i][j] * k_star[j] for j in range(n))
            for i in range(n)
        )
        nearest_d = min(
            math.hypot(p.x_map - x_map, p.y_map - y_map) for p in self.points
        )
        return ResidualPrediction(
            residual_mean_db=mean,
            residual_std_db=math.sqrt(max(var, 1e-6)),
            nearest_measurement_distance_m=nearest_d,
            supporting_measurement_count=n,
        )
