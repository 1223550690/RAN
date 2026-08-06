"""可解释参数校准(环节五):零依赖 Ridge 回归(正规方程)。

模型(文档 9.3):
  PL_calibrated = PL_3gpp
    + beta_0
    + beta_brick·N_brick + beta_glass·N_glass + beta_drywall·N_drywall
    + beta_exterior·N_exterior + beta_indoor·d_indoor + beta_nlos·I_nlos
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from ran.radio.geometry import PropagationGeometry

FEATURE_NAMES = [
    "intercept",
    "brick",
    "glass",
    "drywall",
    "exterior",
    "indoor_distance",
    "nlos",
]


@dataclass(slots=True)
class CalibratedChannelParameters:
    """校准后的参数与不确定性。"""

    model_version: str
    training_measurement_count: int
    intercept_db: float
    material_coefficients: dict[str, float]  # brick/glass/drywall/exterior
    indoor_distance_coefficient: float  # dB/m
    nlos_bias_db: float
    calibration_rmse_db: float
    parameter_uncertainties: dict[str, float]  # 对角 (XᵀX+λI)⁻¹·σ² 开方


def feature_vector(geometry: PropagationGeometry) -> list[float]:
    """从传播几何提取校准特征向量(与 FEATURE_NAMES 对齐)。"""

    brick = glass = drywall = 0
    for crossing in geometry.effective_surface_crossings:
        material = str(getattr(crossing, "material", "") or "").lower()
        if material == "brick":
            brick += 1
        elif material == "glass":
            glass += 1
        elif material == "drywall":
            drywall += 1
    exterior = len(geometry.exterior_surfaces_crossed)
    indoor_m = geometry.indoor_distance_m or 0.0
    nlos = 1.0 if geometry.los_state == "nlos" else 0.0
    return [1.0, float(brick), float(glass), float(drywall), float(exterior), indoor_m, nlos]


def _solve_ridge(X: list[list[float]], y: list[float], lam: float) -> list[float]:
    """正规方程 (XᵀX + λI)β = Xᵀy,高斯消元(特征 ≤8,样本 ≤80,毫秒级)。"""

    n_features = len(X[0])
    n = len(X)
    # A = XᵀX + λI;b = Xᵀy
    A = [[0.0] * n_features for _ in range(n_features)]
    b = [0.0] * n_features
    for i in range(n_features):
        for j in range(n_features):
            s = 0.0
            for k in range(n):
                s += X[k][i] * X[k][j]
            A[i][j] = s
        A[i][i] += lam
        b[i] = sum(X[k][i] * y[k] for k in range(n))
    # 高斯消元(部分主元)
    for col in range(n_features):
        pivot = max(range(col, n_features), key=lambda r: abs(A[r][col]))
        if abs(A[pivot][col]) < 1e-12:
            continue
        A[col], A[pivot] = A[pivot], A[col]
        b[col], b[pivot] = b[pivot], b[col]
        for row in range(col + 1, n_features):
            factor = A[row][col] / A[col][col]
            for j in range(col, n_features):
                A[row][j] -= factor * A[col][j]
            b[row] -= factor * b[col]
    beta = [0.0] * n_features
    for row in range(n_features - 1, -1, -1):
        if abs(A[row][row]) < 1e-12:
            continue
        s = b[row] - sum(A[row][j] * beta[j] for j in range(row + 1, n_features))
        beta[row] = s / A[row][row]
    return beta


def fit_calibration(
    *,
    feature_rows: list[list[float]],
    residual_db: list[float],  # measured_pl - PL_3gpp
    ridge_lambda: float = 0.1,
    model_version: str = "ckm-v1",
) -> CalibratedChannelParameters:
    """拟合校准参数(在参考点上,残差 = 测量 - 物理预测)。"""

    if not feature_rows:
        return CalibratedChannelParameters(
            model_version=model_version,
            training_measurement_count=0,
            intercept_db=0.0,
            material_coefficients={},
            indoor_distance_coefficient=0.0,
            nlos_bias_db=0.0,
            calibration_rmse_db=0.0,
            parameter_uncertainties={},
        )
    beta = _solve_ridge(feature_rows, residual_db, ridge_lambda)
    # RMSE
    rmse = math.sqrt(
        sum(
            (residual_db[i] - sum(beta[j] * feature_rows[i][j] for j in range(len(beta)))) ** 2
            for i in range(len(residual_db))
        )
        / len(residual_db)
    )
    return CalibratedChannelParameters(
        model_version=model_version,
        training_measurement_count=len(residual_db),
        intercept_db=beta[0],
        material_coefficients={
            "brick": beta[1],
            "glass": beta[2],
            "drywall": beta[3],
            "exterior": beta[4],
        },
        indoor_distance_coefficient=beta[5],
        nlos_bias_db=beta[6],
        calibration_rmse_db=rmse,
        parameter_uncertainties={},
    )


def apply_calibration(calibration: CalibratedChannelParameters, features: list[float]) -> float:
    """校准修正量(叠加到物理预测)。"""

    if calibration.training_measurement_count == 0:
        return 0.0
    return (
        calibration.intercept_db
        + calibration.material_coefficients.get("brick", 0.0) * features[1]
        + calibration.material_coefficients.get("glass", 0.0) * features[2]
        + calibration.material_coefficients.get("drywall", 0.0) * features[3]
        + calibration.material_coefficients.get("exterior", 0.0) * features[4]
        + calibration.indoor_distance_coefficient * features[5]
        + calibration.nlos_bias_db * features[6]
    )
