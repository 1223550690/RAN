"""Online spatiotemporal CKM residual estimation.

This module is intentionally independent from the runtime channel pipeline.  It
models only the residual on top of a caller-provided static path-loss baseline:

    residual(x, y, t) = phi(x, y)^T theta(t)

The spatial features are fixed RBFs and the coefficients follow a scalar
Gauss-Markov transition.  Scalar Kalman updates assimilate sparse path-loss
observations.  No scene, ChannelState, scheduler, PHY, or ground-truth module is
imported here, which keeps the experimental estimator isolated and reusable.
"""

from __future__ import annotations

from dataclasses import dataclass
import math


_EPSILON = 1e-12


@dataclass(frozen=True, slots=True)
class OnlineSpatiotemporalConfig:
    """Internal estimator configuration; this is not a shared RAN contract."""

    scene_bounds: tuple[float, float, float, float] = (0.0, 0.0, 2000.0, 2000.0)
    basis_columns: int = 5
    basis_rows: int = 5
    basis_width_map_units: float | None = None
    time_constant_seconds: float = 45.0
    prior_std_db: float = 6.0
    measurement_std_db: float = 1.5
    model_discrepancy_std_db: float = 1.0
    max_correction_db: float = 15.0
    max_prediction_std_db: float = 20.0
    max_observation_residual_db: float = 50.0
    support_radius_map_units: float = 300.0
    support_time_constant_seconds: float = 60.0
    max_support_observations: int = 256

    def __post_init__(self) -> None:
        x0, y0, x1, y1 = self.scene_bounds
        numbers = (
            x0,
            y0,
            x1,
            y1,
            self.time_constant_seconds,
            self.prior_std_db,
            self.measurement_std_db,
            self.model_discrepancy_std_db,
            self.max_correction_db,
            self.max_prediction_std_db,
            self.max_observation_residual_db,
            self.support_radius_map_units,
            self.support_time_constant_seconds,
        )
        if not all(math.isfinite(value) for value in numbers):
            raise ValueError("online CKM configuration values must be finite")
        if x1 <= x0 or y1 <= y0:
            raise ValueError("scene_bounds must have positive width and height")
        if self.basis_columns <= 0 or self.basis_rows <= 0:
            raise ValueError("basis_columns and basis_rows must be positive")
        if self.basis_width_map_units is not None:
            if not math.isfinite(self.basis_width_map_units) or self.basis_width_map_units <= 0.0:
                raise ValueError("basis_width_map_units must be positive when supplied")
        if self.time_constant_seconds <= 0.0:
            raise ValueError("time_constant_seconds must be positive")
        if self.prior_std_db <= 0.0 or self.measurement_std_db <= 0.0:
            raise ValueError("prior and measurement standard deviations must be positive")
        if self.model_discrepancy_std_db < 0.0:
            raise ValueError("model_discrepancy_std_db must be non-negative")
        if self.max_correction_db <= 0.0 or self.max_prediction_std_db <= 0.0:
            raise ValueError("prediction limits must be positive")
        if self.max_observation_residual_db <= 0.0:
            raise ValueError("max_observation_residual_db must be positive")
        if self.support_radius_map_units <= 0.0 or self.support_time_constant_seconds <= 0.0:
            raise ValueError("support radius and time constant must be positive")
        if self.max_support_observations <= 0:
            raise ValueError("max_support_observations must be positive")


@dataclass(frozen=True, slots=True)
class CkmObservation:
    """One independent path-loss observation used by the online estimator."""

    observation_id: str
    elapsed_seconds: float
    scene_id: str
    gnb_id: str
    carrier_freq_mhz: float
    x_map: float
    y_map: float
    baseline_path_loss_db: float
    observed_path_loss_db: float
    source: str = "controlled_oracle"
    quality: float = 1.0


@dataclass(frozen=True, slots=True)
class CkmObservationUpdate:
    accepted: bool
    observation_count: int
    innovation_db: float | None = None
    gain_norm: float | None = None
    rejection_reason: str | None = None


@dataclass(frozen=True, slots=True)
class SpatiotemporalCkmPrediction:
    accepted: bool
    selected_path_loss_db: float
    baseline_path_loss_db: float
    residual_mean_db: float
    residual_std_db: float
    observation_count: int
    elapsed_since_update_s: float | None
    support_score: float
    fallback_reason: str | None = None


class OnlineSpatiotemporalResidualModel:
    """Low-rank dynamic residual model with scalar Kalman updates.

    One instance is bound to a single (scene, gNB, carrier) link key.  Querying
    never mutates the model; only a successfully accepted observation advances
    state time and updates coefficients.
    """

    def __init__(
        self,
        *,
        scene_id: str,
        gnb_id: str,
        carrier_freq_mhz: float,
        config: OnlineSpatiotemporalConfig | None = None,
    ) -> None:
        if not scene_id or not gnb_id:
            raise ValueError("scene_id and gnb_id must be non-empty")
        if not math.isfinite(carrier_freq_mhz) or carrier_freq_mhz <= 0.0:
            raise ValueError("carrier_freq_mhz must be positive and finite")
        self.scene_id = scene_id
        self.gnb_id = gnb_id
        self.carrier_freq_mhz = float(carrier_freq_mhz)
        self.config = config or OnlineSpatiotemporalConfig()
        self._centers, self._basis_width = _build_basis(self.config)
        self._dimension = len(self._centers)
        self._theta = [0.0] * self._dimension
        prior_variance = self.config.prior_std_db**2
        self._covariance = [
            [prior_variance if row == column else 0.0 for column in range(self._dimension)]
            for row in range(self._dimension)
        ]
        self._last_update_seconds: float | None = None
        self._observation_count = 0
        self._observation_ids: set[str] = set()
        self._support_observations: list[tuple[float, float, float]] = []

    @property
    def observation_count(self) -> int:
        return self._observation_count

    @property
    def feature_count(self) -> int:
        return self._dimension

    @property
    def last_update_seconds(self) -> float | None:
        return self._last_update_seconds

    def predict_at(
        self,
        *,
        elapsed_seconds: float,
        x_map: float,
        y_map: float,
        baseline_path_loss_db: float,
        scene_id: str | None = None,
        gnb_id: str | None = None,
        carrier_freq_mhz: float | None = None,
    ) -> SpatiotemporalCkmPrediction:
        """Predict before observing; this method never changes internal state."""

        invalid = self._prediction_rejection_reason(
            elapsed_seconds=elapsed_seconds,
            x_map=x_map,
            y_map=y_map,
            baseline_path_loss_db=baseline_path_loss_db,
            scene_id=scene_id,
            gnb_id=gnb_id,
            carrier_freq_mhz=carrier_freq_mhz,
        )
        if invalid is not None:
            return self._fallback_prediction(
                baseline_path_loss_db=baseline_path_loss_db,
                elapsed_seconds=elapsed_seconds,
                reason=invalid,
            )

        features = self._features(x_map, y_map)
        theta, covariance = self._predicted_state(elapsed_seconds)
        residual_mean = _dot(features, theta)
        residual_variance = max(_quadratic_form(features, covariance), 0.0)
        residual_std = math.sqrt(
            residual_variance + self.config.model_discrepancy_std_db**2
        )
        if self._observation_count == 0:
            return self._fallback_prediction(
                baseline_path_loss_db=baseline_path_loss_db,
                elapsed_seconds=elapsed_seconds,
                residual_std_db=residual_std,
                reason="no_observations",
            )
        if not math.isfinite(residual_mean) or not math.isfinite(residual_std):
            return self._fallback_prediction(
                baseline_path_loss_db=baseline_path_loss_db,
                elapsed_seconds=elapsed_seconds,
                reason="non_finite_prediction",
            )
        if residual_std > self.config.max_prediction_std_db:
            return self._fallback_prediction(
                baseline_path_loss_db=baseline_path_loss_db,
                elapsed_seconds=elapsed_seconds,
                residual_std_db=residual_std,
                reason="prediction_uncertainty_exceeds_limit",
            )

        support_score = self._support_score(x_map, y_map, elapsed_seconds)
        clipped_mean = _clip(
            residual_mean * support_score,
            -self.config.max_correction_db,
            self.config.max_correction_db,
        )
        return SpatiotemporalCkmPrediction(
            accepted=True,
            selected_path_loss_db=baseline_path_loss_db + clipped_mean,
            baseline_path_loss_db=baseline_path_loss_db,
            residual_mean_db=clipped_mean,
            residual_std_db=residual_std,
            observation_count=self._observation_count,
            elapsed_since_update_s=self._elapsed_since_update(elapsed_seconds),
            support_score=support_score,
        )

    def observe(self, observation: CkmObservation) -> CkmObservationUpdate:
        """Assimilate one observation, rejecting invalid input without mutation."""

        reason = self._observation_rejection_reason(observation)
        if reason is not None:
            return CkmObservationUpdate(
                accepted=False,
                observation_count=self._observation_count,
                rejection_reason=reason,
            )

        features = self._features(observation.x_map, observation.y_map)
        theta_pred, covariance_pred = self._predicted_state(observation.elapsed_seconds)
        target_residual = observation.observed_path_loss_db - observation.baseline_path_loss_db
        predicted_residual = _dot(features, theta_pred)
        innovation = target_residual - predicted_residual
        projected_covariance = _matrix_vector(covariance_pred, features)
        measurement_variance = self.config.measurement_std_db**2 / observation.quality
        innovation_variance = _dot(features, projected_covariance) + measurement_variance
        if not math.isfinite(innovation_variance) or innovation_variance <= _EPSILON:
            return CkmObservationUpdate(
                accepted=False,
                observation_count=self._observation_count,
                rejection_reason="invalid_innovation_variance",
            )
        gain = [value / innovation_variance for value in projected_covariance]
        theta_new = [
            theta_pred[index] + gain[index] * innovation
            for index in range(self._dimension)
        ]

        # Scalar Kalman covariance update: P - (P H^T)(P H^T)^T / S.
        # Symmetrisation and a small diagonal floor prevent round-off drift.
        covariance_new = [[0.0] * self._dimension for _ in range(self._dimension)]
        for row in range(self._dimension):
            for column in range(self._dimension):
                value = covariance_pred[row][column] - (
                    projected_covariance[row] * projected_covariance[column] / innovation_variance
                )
                covariance_new[row][column] = value
        _symmetrise_and_floor(covariance_new)

        if not _all_finite(theta_new) or not _matrix_all_finite(covariance_new):
            return CkmObservationUpdate(
                accepted=False,
                observation_count=self._observation_count,
                rejection_reason="non_finite_updated_state",
            )

        self._theta = theta_new
        self._covariance = covariance_new
        self._last_update_seconds = observation.elapsed_seconds
        self._observation_count += 1
        self._observation_ids.add(observation.observation_id)
        self._support_observations.append(
            (observation.x_map, observation.y_map, observation.elapsed_seconds)
        )
        if len(self._support_observations) > self.config.max_support_observations:
            self._support_observations = self._support_observations[
                -self.config.max_support_observations :
            ]
        return CkmObservationUpdate(
            accepted=True,
            observation_count=self._observation_count,
            innovation_db=innovation,
            gain_norm=math.sqrt(sum(value * value for value in gain)),
        )

    def _features(self, x_map: float, y_map: float) -> list[float]:
        values = [
            math.exp(-((x_map - center_x) ** 2 + (y_map - center_y) ** 2) / (2.0 * self._basis_width**2))
            for center_x, center_y in self._centers
        ]
        norm = math.sqrt(sum(value * value for value in values))
        if norm <= _EPSILON:
            # This can occur only far outside configured bounds, which callers
            # reject before feature extraction.  Keep a deterministic fallback.
            values[0] = 1.0
            norm = 1.0
        return [value / norm for value in values]

    def _predicted_state(self, elapsed_seconds: float) -> tuple[list[float], list[list[float]]]:
        if self._last_update_seconds is None:
            return list(self._theta), [list(row) for row in self._covariance]
        delta = max(0.0, elapsed_seconds - self._last_update_seconds)
        transition = math.exp(-delta / self.config.time_constant_seconds)
        transition_sq = transition * transition
        theta = [transition * value for value in self._theta]
        prior_variance = self.config.prior_std_db**2
        covariance = [[0.0] * self._dimension for _ in range(self._dimension)]
        for row in range(self._dimension):
            for column in range(self._dimension):
                value = transition_sq * self._covariance[row][column]
                if row == column:
                    value += (1.0 - transition_sq) * prior_variance
                covariance[row][column] = value
        return theta, covariance

    def _prediction_rejection_reason(
        self,
        *,
        elapsed_seconds: float,
        x_map: float,
        y_map: float,
        baseline_path_loss_db: float,
        scene_id: str | None,
        gnb_id: str | None,
        carrier_freq_mhz: float | None,
    ) -> str | None:
        if not all(math.isfinite(value) for value in (elapsed_seconds, x_map, y_map, baseline_path_loss_db)):
            return "non_finite_prediction_input"
        if elapsed_seconds < 0.0:
            return "negative_elapsed_seconds"
        if self._last_update_seconds is not None and elapsed_seconds + _EPSILON < self._last_update_seconds:
            return "prediction_time_before_model_state"
        if not self._inside_bounds(x_map, y_map):
            return "position_outside_scene_bounds"
        if scene_id is not None and scene_id != self.scene_id:
            return "scene_id_mismatch"
        if gnb_id is not None and gnb_id != self.gnb_id:
            return "gnb_id_mismatch"
        if carrier_freq_mhz is not None:
            if not math.isfinite(carrier_freq_mhz):
                return "non_finite_carrier_frequency"
            if not math.isclose(carrier_freq_mhz, self.carrier_freq_mhz, rel_tol=0.0, abs_tol=1e-9):
                return "carrier_frequency_mismatch"
        return None

    def _observation_rejection_reason(self, observation: CkmObservation) -> str | None:
        if not observation.observation_id:
            return "missing_observation_id"
        if observation.observation_id in self._observation_ids:
            return "duplicate_observation_id"
        if not observation.source:
            return "missing_observation_source"
        if observation.scene_id != self.scene_id:
            return "scene_id_mismatch"
        if observation.gnb_id != self.gnb_id:
            return "gnb_id_mismatch"
        if not math.isclose(
            observation.carrier_freq_mhz,
            self.carrier_freq_mhz,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            return "carrier_frequency_mismatch"
        values = (
            observation.elapsed_seconds,
            observation.carrier_freq_mhz,
            observation.x_map,
            observation.y_map,
            observation.baseline_path_loss_db,
            observation.observed_path_loss_db,
            observation.quality,
        )
        if not all(math.isfinite(value) for value in values):
            return "non_finite_observation"
        if observation.elapsed_seconds < 0.0:
            return "negative_elapsed_seconds"
        if self._last_update_seconds is not None:
            if observation.elapsed_seconds + _EPSILON < self._last_update_seconds:
                return "observation_time_before_model_state"
        if not self._inside_bounds(observation.x_map, observation.y_map):
            return "position_outside_scene_bounds"
        if not 0.0 < observation.quality <= 1.0:
            return "quality_out_of_range"
        residual = observation.observed_path_loss_db - observation.baseline_path_loss_db
        if abs(residual) > self.config.max_observation_residual_db:
            return "observation_residual_exceeds_limit"
        return None

    def _inside_bounds(self, x_map: float, y_map: float) -> bool:
        x0, y0, x1, y1 = self.config.scene_bounds
        return x0 <= x_map <= x1 and y0 <= y_map <= y1

    def _elapsed_since_update(self, elapsed_seconds: float) -> float | None:
        if self._last_update_seconds is None:
            return None
        return max(0.0, elapsed_seconds - self._last_update_seconds)

    def _support_score(self, x_map: float, y_map: float, elapsed_seconds: float) -> float:
        """Bound online corrections to regions supported by recent evidence."""

        best = 0.0
        radius = self.config.support_radius_map_units
        time_constant = self.config.support_time_constant_seconds
        for observed_x, observed_y, observed_seconds in self._support_observations:
            age = elapsed_seconds - observed_seconds
            if age < 0.0:
                continue
            distance = math.hypot(x_map - observed_x, y_map - observed_y)
            spatial = math.exp(-0.5 * (distance / radius) ** 2)
            temporal = math.exp(-age / time_constant)
            best = max(best, spatial * temporal)
        return _clip(best, 0.0, 1.0)

    def _fallback_prediction(
        self,
        *,
        baseline_path_loss_db: float,
        elapsed_seconds: float,
        reason: str,
        residual_std_db: float | None = None,
    ) -> SpatiotemporalCkmPrediction:
        std = self.config.prior_std_db if residual_std_db is None else residual_std_db
        baseline = baseline_path_loss_db if math.isfinite(baseline_path_loss_db) else 0.0
        return SpatiotemporalCkmPrediction(
            accepted=False,
            selected_path_loss_db=baseline,
            baseline_path_loss_db=baseline,
            residual_mean_db=0.0,
            residual_std_db=std,
            observation_count=self._observation_count,
            elapsed_since_update_s=(
                self._elapsed_since_update(elapsed_seconds)
                if math.isfinite(elapsed_seconds)
                else None
            ),
            support_score=0.0,
            fallback_reason=reason,
        )


def _build_basis(
    config: OnlineSpatiotemporalConfig,
) -> tuple[list[tuple[float, float]], float]:
    x0, y0, x1, y1 = config.scene_bounds
    column_spacing = (x1 - x0) / config.basis_columns
    row_spacing = (y1 - y0) / config.basis_rows
    centers = [
        (
            x0 + (column + 0.5) * column_spacing,
            y0 + (row + 0.5) * row_spacing,
        )
        for row in range(config.basis_rows)
        for column in range(config.basis_columns)
    ]
    width = config.basis_width_map_units
    if width is None:
        width = 1.5 * max(column_spacing, row_spacing)
    return centers, float(width)


def _dot(a: list[float], b: list[float]) -> float:
    return sum(left * right for left, right in zip(a, b))


def _matrix_vector(matrix: list[list[float]], vector: list[float]) -> list[float]:
    return [_dot(row, vector) for row in matrix]


def _quadratic_form(vector: list[float], matrix: list[list[float]]) -> float:
    return _dot(vector, _matrix_vector(matrix, vector))


def _clip(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _all_finite(values: list[float]) -> bool:
    return all(math.isfinite(value) for value in values)


def _matrix_all_finite(matrix: list[list[float]]) -> bool:
    return all(_all_finite(row) for row in matrix)


def _symmetrise_and_floor(matrix: list[list[float]]) -> None:
    size = len(matrix)
    for row in range(size):
        matrix[row][row] = max(matrix[row][row], _EPSILON)
        for column in range(row + 1, size):
            value = 0.5 * (matrix[row][column] + matrix[column][row])
            matrix[row][column] = value
            matrix[column][row] = value


__all__ = [
    "CkmObservation",
    "CkmObservationUpdate",
    "OnlineSpatiotemporalConfig",
    "OnlineSpatiotemporalResidualModel",
    "SpatiotemporalCkmPrediction",
]
