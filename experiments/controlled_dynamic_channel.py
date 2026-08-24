"""Independent controlled dynamic-channel oracle for CKM experiments.

The oracle deliberately lives under ``experiments`` and does not import the
online estimator.  It produces a hidden low-rank spatial field, a correlated
temporal field, and an optional local event on top of a caller-provided static
path-loss baseline.  Only sparse samples selected by an experiment harness are
exposed to the estimator.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import random


@dataclass(frozen=True, slots=True)
class ControlledEventConfig:
    center_x_map: float = 1050.0
    center_y_map: float = 950.0
    radius_map_units: float = 180.0
    max_loss_db: float = 8.0
    start_seconds: float = 40.0
    ramp_seconds: float = 10.0
    active_seconds: float = 40.0
    recovery_seconds: float = 20.0

    def __post_init__(self) -> None:
        values = (
            self.center_x_map,
            self.center_y_map,
            self.radius_map_units,
            self.max_loss_db,
            self.start_seconds,
            self.ramp_seconds,
            self.active_seconds,
            self.recovery_seconds,
        )
        if not all(math.isfinite(value) for value in values):
            raise ValueError("controlled event values must be finite")
        if self.radius_map_units <= 0.0:
            raise ValueError("event radius must be positive")
        if self.max_loss_db < 0.0 or self.start_seconds < 0.0:
            raise ValueError("event loss and start time must be non-negative")
        if self.ramp_seconds < 0.0 or self.active_seconds < 0.0 or self.recovery_seconds < 0.0:
            raise ValueError("event durations must be non-negative")


@dataclass(frozen=True, slots=True)
class ControlledDynamicChannelConfig:
    seed: int = 9042
    static_feature_count: int = 48
    temporal_feature_count: int = 40
    static_std_db: float = 2.5
    temporal_std_db: float = 3.0
    measurement_std_db: float = 1.0
    coherence_time_seconds: float = 35.0
    min_spatial_scale_map_units: float = 90.0
    max_spatial_scale_map_units: float = 550.0
    event: ControlledEventConfig | None = ControlledEventConfig()

    def __post_init__(self) -> None:
        values = (
            self.static_std_db,
            self.temporal_std_db,
            self.measurement_std_db,
            self.coherence_time_seconds,
            self.min_spatial_scale_map_units,
            self.max_spatial_scale_map_units,
        )
        if not all(math.isfinite(value) for value in values):
            raise ValueError("dynamic-channel configuration values must be finite")
        if self.static_feature_count <= 0 or self.temporal_feature_count <= 0:
            raise ValueError("truth feature counts must be positive")
        if self.static_std_db < 0.0 or self.temporal_std_db < 0.0:
            raise ValueError("truth field standard deviations must be non-negative")
        if self.measurement_std_db < 0.0:
            raise ValueError("measurement_std_db must be non-negative")
        if self.coherence_time_seconds <= 0.0:
            raise ValueError("coherence_time_seconds must be positive")
        if self.min_spatial_scale_map_units <= 0.0:
            raise ValueError("minimum spatial scale must be positive")
        if self.max_spatial_scale_map_units < self.min_spatial_scale_map_units:
            raise ValueError("maximum spatial scale must not be smaller than minimum")


@dataclass(frozen=True, slots=True)
class DynamicTruthSample:
    elapsed_seconds: float
    x_map: float
    y_map: float
    baseline_path_loss_db: float
    static_hidden_residual_db: float
    temporal_hidden_residual_db: float
    event_loss_db: float
    truth_path_loss_db: float


@dataclass(frozen=True, slots=True)
class DynamicObservationSample:
    observation_id: str
    truth: DynamicTruthSample
    measurement_noise_db: float
    observed_path_loss_db: float


@dataclass(frozen=True, slots=True)
class _FourierFeature:
    omega_x: float
    omega_y: float
    phase: float

    def value(self, x_map: float, y_map: float) -> float:
        return math.cos(self.omega_x * x_map + self.omega_y * y_map + self.phase)


class ControlledDynamicChannel:
    """Stateful, deterministic oracle with monotonic elapsed time."""

    def __init__(self, config: ControlledDynamicChannelConfig | None = None) -> None:
        self.config = config or ControlledDynamicChannelConfig()
        self._rng = random.Random(self.config.seed)
        self._static_features = self._make_features(self.config.static_feature_count)
        self._temporal_features = self._make_features(self.config.temporal_feature_count)
        self._static_coefficients = self._initial_coefficients(
            self.config.static_feature_count,
            self.config.static_std_db,
        )
        self._temporal_coefficients = self._initial_coefficients(
            self.config.temporal_feature_count,
            self.config.temporal_std_db,
        )
        self._elapsed_seconds: float | None = None

    @property
    def elapsed_seconds(self) -> float | None:
        return self._elapsed_seconds

    def advance_to(self, elapsed_seconds: float) -> None:
        """Advance hidden temporal coefficients; time must be monotonic."""

        if not math.isfinite(elapsed_seconds) or elapsed_seconds < 0.0:
            raise ValueError("elapsed_seconds must be finite and non-negative")
        if self._elapsed_seconds is None:
            self._elapsed_seconds = elapsed_seconds
            return
        if elapsed_seconds < self._elapsed_seconds:
            raise ValueError("controlled dynamic-channel time cannot move backwards")
        delta = elapsed_seconds - self._elapsed_seconds
        if delta <= 0.0:
            return
        rho = math.exp(-delta / self.config.coherence_time_seconds)
        innovation_scale = math.sqrt(max(0.0, 1.0 - rho * rho))
        coefficient_std = _coefficient_std(
            self.config.temporal_std_db,
            self.config.temporal_feature_count,
        )
        self._temporal_coefficients = [
            rho * value + innovation_scale * self._rng.gauss(0.0, coefficient_std)
            for value in self._temporal_coefficients
        ]
        self._elapsed_seconds = elapsed_seconds

    def query_truth(
        self,
        *,
        elapsed_seconds: float,
        x_map: float,
        y_map: float,
        baseline_path_loss_db: float,
    ) -> DynamicTruthSample:
        if not all(math.isfinite(value) for value in (x_map, y_map, baseline_path_loss_db)):
            raise ValueError("truth query inputs must be finite")
        self.advance_to(elapsed_seconds)
        static_residual = _field_value(
            self._static_features,
            self._static_coefficients,
            x_map,
            y_map,
        )
        temporal_residual = _field_value(
            self._temporal_features,
            self._temporal_coefficients,
            x_map,
            y_map,
        )
        event_loss = self._event_loss(x_map, y_map, elapsed_seconds)
        truth_path_loss = baseline_path_loss_db + static_residual + temporal_residual + event_loss
        return DynamicTruthSample(
            elapsed_seconds=elapsed_seconds,
            x_map=x_map,
            y_map=y_map,
            baseline_path_loss_db=baseline_path_loss_db,
            static_hidden_residual_db=static_residual,
            temporal_hidden_residual_db=temporal_residual,
            event_loss_db=event_loss,
            truth_path_loss_db=truth_path_loss,
        )

    def sample_observation(
        self,
        *,
        observation_id: str,
        elapsed_seconds: float,
        x_map: float,
        y_map: float,
        baseline_path_loss_db: float,
    ) -> DynamicObservationSample:
        if not observation_id:
            raise ValueError("observation_id must be non-empty")
        truth = self.query_truth(
            elapsed_seconds=elapsed_seconds,
            x_map=x_map,
            y_map=y_map,
            baseline_path_loss_db=baseline_path_loss_db,
        )
        noise = self._measurement_noise(observation_id)
        return DynamicObservationSample(
            observation_id=observation_id,
            truth=truth,
            measurement_noise_db=noise,
            observed_path_loss_db=truth.truth_path_loss_db + noise,
        )

    def _make_features(self, count: int) -> list[_FourierFeature]:
        features = []
        for _ in range(count):
            log_min = math.log(self.config.min_spatial_scale_map_units)
            log_max = math.log(self.config.max_spatial_scale_map_units)
            spatial_scale = math.exp(self._rng.uniform(log_min, log_max))
            angular_frequency = 2.0 * math.pi / spatial_scale
            direction = self._rng.uniform(0.0, 2.0 * math.pi)
            features.append(
                _FourierFeature(
                    omega_x=angular_frequency * math.cos(direction),
                    omega_y=angular_frequency * math.sin(direction),
                    phase=self._rng.uniform(0.0, 2.0 * math.pi),
                )
            )
        return features

    def _initial_coefficients(self, count: int, field_std_db: float) -> list[float]:
        std = _coefficient_std(field_std_db, count)
        return [self._rng.gauss(0.0, std) for _ in range(count)]

    def _measurement_noise(self, observation_id: str) -> float:
        if self.config.measurement_std_db == 0.0:
            return 0.0
        digest = hashlib.sha256(
            f"{self.config.seed}:{observation_id}".encode("utf-8")
        ).digest()
        rng = random.Random(int.from_bytes(digest[:8], "big", signed=False))
        return rng.gauss(0.0, self.config.measurement_std_db)

    def _event_loss(self, x_map: float, y_map: float, elapsed_seconds: float) -> float:
        event = self.config.event
        if event is None:
            return 0.0
        amplitude = _event_amplitude(event, elapsed_seconds)
        if amplitude <= 0.0:
            return 0.0
        distance_sq = (x_map - event.center_x_map) ** 2 + (y_map - event.center_y_map) ** 2
        spatial_weight = math.exp(-distance_sq / (2.0 * event.radius_map_units**2))
        return amplitude * spatial_weight


def _coefficient_std(field_std_db: float, feature_count: int) -> float:
    # For random phases E[cos^2] = 1/2, so this scale gives approximately the
    # requested pointwise field standard deviation.
    if field_std_db == 0.0:
        return 0.0
    return field_std_db * math.sqrt(2.0 / feature_count)


def _field_value(
    features: list[_FourierFeature],
    coefficients: list[float],
    x_map: float,
    y_map: float,
) -> float:
    return sum(
        coefficient * feature.value(x_map, y_map)
        for feature, coefficient in zip(features, coefficients)
    )


def _event_amplitude(event: ControlledEventConfig, elapsed_seconds: float) -> float:
    start = event.start_seconds
    ramp_end = start + event.ramp_seconds
    active_end = ramp_end + event.active_seconds
    recovery_end = active_end + event.recovery_seconds
    if elapsed_seconds < start:
        return 0.0
    if event.ramp_seconds > 0.0 and elapsed_seconds < ramp_end:
        return event.max_loss_db * (elapsed_seconds - start) / event.ramp_seconds
    if elapsed_seconds < active_end:
        return event.max_loss_db
    if event.recovery_seconds > 0.0 and elapsed_seconds < recovery_end:
        return event.max_loss_db * (1.0 - (elapsed_seconds - active_end) / event.recovery_seconds)
    return 0.0


__all__ = [
    "ControlledDynamicChannel",
    "ControlledDynamicChannelConfig",
    "ControlledEventConfig",
    "DynamicObservationSample",
    "DynamicTruthSample",
]
