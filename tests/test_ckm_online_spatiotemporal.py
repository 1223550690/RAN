"""Tests for the isolated online spatiotemporal CKM experiment modules."""

from __future__ import annotations

import math
import unittest

from experiments.controlled_dynamic_channel import (
    ControlledDynamicChannel,
    ControlledDynamicChannelConfig,
    ControlledEventConfig,
)
from ran.ckm.online_spatiotemporal import (
    CkmObservation,
    OnlineSpatiotemporalConfig,
    OnlineSpatiotemporalResidualModel,
)


def _model(
    *,
    config: OnlineSpatiotemporalConfig | None = None,
) -> OnlineSpatiotemporalResidualModel:
    return OnlineSpatiotemporalResidualModel(
        scene_id="scene",
        gnb_id="gnb",
        carrier_freq_mhz=3500.0,
        config=config
        or OnlineSpatiotemporalConfig(
            scene_bounds=(0.0, 0.0, 100.0, 100.0),
            basis_columns=2,
            basis_rows=2,
            time_constant_seconds=20.0,
            prior_std_db=6.0,
            measurement_std_db=0.5,
        ),
    )


def _observation(
    observation_id: str,
    *,
    elapsed_seconds: float = 0.0,
    x_map: float = 25.0,
    y_map: float = 25.0,
    baseline: float = 100.0,
    observed: float = 108.0,
    quality: float = 1.0,
) -> CkmObservation:
    return CkmObservation(
        observation_id=observation_id,
        elapsed_seconds=elapsed_seconds,
        scene_id="scene",
        gnb_id="gnb",
        carrier_freq_mhz=3500.0,
        x_map=x_map,
        y_map=y_map,
        baseline_path_loss_db=baseline,
        observed_path_loss_db=observed,
        quality=quality,
    )


class OnlineSpatiotemporalResidualTests(unittest.TestCase):
    def test_no_observation_falls_back_exactly_to_static_baseline(self) -> None:
        model = _model()
        prediction = model.predict_at(
            elapsed_seconds=0.0,
            x_map=25.0,
            y_map=25.0,
            baseline_path_loss_db=101.5,
        )
        self.assertFalse(prediction.accepted)
        self.assertEqual(prediction.fallback_reason, "no_observations")
        self.assertEqual(prediction.selected_path_loss_db, 101.5)
        self.assertEqual(prediction.residual_mean_db, 0.0)

    def test_observation_reduces_local_error(self) -> None:
        config = OnlineSpatiotemporalConfig(
            scene_bounds=(0.0, 0.0, 100.0, 100.0),
            basis_columns=1,
            basis_rows=1,
            prior_std_db=8.0,
            measurement_std_db=0.1,
            time_constant_seconds=100.0,
        )
        model = _model(config=config)
        before = model.predict_at(
            elapsed_seconds=0.0,
            x_map=50.0,
            y_map=50.0,
            baseline_path_loss_db=100.0,
        )
        update = model.observe(
            _observation("obs-1", x_map=50.0, y_map=50.0, observed=108.0)
        )
        after = model.predict_at(
            elapsed_seconds=0.0,
            x_map=50.0,
            y_map=50.0,
            baseline_path_loss_db=100.0,
        )
        self.assertTrue(update.accepted)
        self.assertTrue(after.accepted)
        self.assertGreater(abs(before.selected_path_loss_db - 108.0), abs(after.selected_path_loss_db - 108.0))
        self.assertAlmostEqual(after.selected_path_loss_db, 108.0, delta=0.1)

    def test_prediction_does_not_advance_model_time(self) -> None:
        model = _model()
        self.assertTrue(model.observe(_observation("obs-1", elapsed_seconds=0.0)).accepted)
        future = model.predict_at(
            elapsed_seconds=50.0,
            x_map=25.0,
            y_map=25.0,
            baseline_path_loss_db=100.0,
        )
        self.assertTrue(future.accepted)
        self.assertEqual(model.last_update_seconds, 0.0)
        # An observation between the previous state and the future query is
        # accepted because predict_at() is read-only.
        update = model.observe(_observation("obs-2", elapsed_seconds=5.0))
        self.assertTrue(update.accepted)
        self.assertEqual(model.last_update_seconds, 5.0)

    def test_mean_decays_and_uncertainty_grows_without_observations(self) -> None:
        model = _model()
        self.assertTrue(model.observe(_observation("obs-1", elapsed_seconds=0.0)).accepted)
        near = model.predict_at(
            elapsed_seconds=0.0,
            x_map=25.0,
            y_map=25.0,
            baseline_path_loss_db=100.0,
        )
        far_time = model.predict_at(
            elapsed_seconds=100.0,
            x_map=25.0,
            y_map=25.0,
            baseline_path_loss_db=100.0,
        )
        self.assertLess(abs(far_time.residual_mean_db), abs(near.residual_mean_db))
        self.assertGreater(far_time.residual_std_db, near.residual_std_db)

    def test_duplicate_and_time_reversal_are_rejected_without_mutation(self) -> None:
        model = _model()
        first = model.observe(_observation("obs-1", elapsed_seconds=10.0))
        self.assertTrue(first.accepted)
        duplicate = model.observe(_observation("obs-1", elapsed_seconds=10.0))
        reversed_time = model.observe(_observation("obs-2", elapsed_seconds=9.0))
        self.assertFalse(duplicate.accepted)
        self.assertEqual(duplicate.rejection_reason, "duplicate_observation_id")
        self.assertFalse(reversed_time.accepted)
        self.assertEqual(reversed_time.rejection_reason, "observation_time_before_model_state")
        self.assertEqual(model.observation_count, 1)
        self.assertEqual(model.last_update_seconds, 10.0)

    def test_non_finite_observation_is_rejected(self) -> None:
        model = _model()
        invalid = _observation("obs-nan", observed=float("nan"))
        result = model.observe(invalid)
        self.assertFalse(result.accepted)
        self.assertEqual(result.rejection_reason, "non_finite_observation")
        self.assertEqual(model.observation_count, 0)

    def test_link_key_mismatch_is_rejected(self) -> None:
        model = _model()
        invalid = CkmObservation(
            observation_id="wrong-link",
            elapsed_seconds=0.0,
            scene_id="other",
            gnb_id="gnb",
            carrier_freq_mhz=3500.0,
            x_map=25.0,
            y_map=25.0,
            baseline_path_loss_db=100.0,
            observed_path_loss_db=105.0,
        )
        result = model.observe(invalid)
        self.assertFalse(result.accepted)
        self.assertEqual(result.rejection_reason, "scene_id_mismatch")

    def test_correction_is_clipped(self) -> None:
        config = OnlineSpatiotemporalConfig(
            scene_bounds=(0.0, 0.0, 100.0, 100.0),
            basis_columns=1,
            basis_rows=1,
            prior_std_db=50.0,
            measurement_std_db=0.01,
            max_correction_db=5.0,
            max_observation_residual_db=100.0,
        )
        model = _model(config=config)
        self.assertTrue(model.observe(_observation("large", x_map=50.0, y_map=50.0, observed=130.0)).accepted)
        prediction = model.predict_at(
            elapsed_seconds=0.0,
            x_map=50.0,
            y_map=50.0,
            baseline_path_loss_db=100.0,
        )
        self.assertEqual(prediction.residual_mean_db, 5.0)
        self.assertEqual(prediction.selected_path_loss_db, 105.0)

    def test_spatial_basis_has_stronger_effect_near_observation(self) -> None:
        config = OnlineSpatiotemporalConfig(
            scene_bounds=(0.0, 0.0, 100.0, 100.0),
            basis_columns=3,
            basis_rows=1,
            basis_width_map_units=18.0,
            prior_std_db=8.0,
            measurement_std_db=0.1,
            time_constant_seconds=100.0,
        )
        model = _model(config=config)
        self.assertTrue(model.observe(_observation("left", x_map=10.0, y_map=50.0, observed=108.0)).accepted)
        near = model.predict_at(
            elapsed_seconds=0.0,
            x_map=10.0,
            y_map=50.0,
            baseline_path_loss_db=100.0,
        )
        far = model.predict_at(
            elapsed_seconds=0.0,
            x_map=90.0,
            y_map=50.0,
            baseline_path_loss_db=100.0,
        )
        self.assertGreater(abs(near.residual_mean_db), abs(far.residual_mean_db))
        self.assertGreater(near.support_score, far.support_score)

    def test_same_observation_sequence_is_deterministic(self) -> None:
        first = _model()
        second = _model()
        for index, elapsed in enumerate((0.0, 2.0, 8.0)):
            observation = _observation(f"obs-{index}", elapsed_seconds=elapsed, observed=105.0 + index)
            self.assertTrue(first.observe(observation).accepted)
            self.assertTrue(second.observe(observation).accepted)
        first_prediction = first.predict_at(
            elapsed_seconds=12.0,
            x_map=40.0,
            y_map=60.0,
            baseline_path_loss_db=100.0,
        )
        second_prediction = second.predict_at(
            elapsed_seconds=12.0,
            x_map=40.0,
            y_map=60.0,
            baseline_path_loss_db=100.0,
        )
        self.assertEqual(first_prediction, second_prediction)


class ControlledDynamicChannelTests(unittest.TestCase):
    def test_same_seed_and_queries_are_deterministic(self) -> None:
        config = ControlledDynamicChannelConfig(seed=17, event=None)
        first = ControlledDynamicChannel(config)
        second = ControlledDynamicChannel(config)
        for elapsed in (0.0, 1.0, 5.0, 20.0):
            a = first.query_truth(
                elapsed_seconds=elapsed,
                x_map=100.0,
                y_map=200.0,
                baseline_path_loss_db=90.0,
            )
            b = second.query_truth(
                elapsed_seconds=elapsed,
                x_map=100.0,
                y_map=200.0,
                baseline_path_loss_db=90.0,
            )
            self.assertEqual(a, b)

    def test_temporal_field_changes_at_same_position(self) -> None:
        oracle = ControlledDynamicChannel(
            ControlledDynamicChannelConfig(
                seed=19,
                static_std_db=0.0,
                temporal_std_db=4.0,
                measurement_std_db=0.0,
                coherence_time_seconds=2.0,
                event=None,
            )
        )
        first = oracle.query_truth(
            elapsed_seconds=0.0,
            x_map=100.0,
            y_map=100.0,
            baseline_path_loss_db=90.0,
        )
        later = oracle.query_truth(
            elapsed_seconds=20.0,
            x_map=100.0,
            y_map=100.0,
            baseline_path_loss_db=90.0,
        )
        self.assertNotAlmostEqual(
            first.temporal_hidden_residual_db,
            later.temporal_hidden_residual_db,
            places=6,
        )

    def test_controlled_event_appears_and_recovers(self) -> None:
        event = ControlledEventConfig(
            center_x_map=10.0,
            center_y_map=10.0,
            radius_map_units=20.0,
            max_loss_db=8.0,
            start_seconds=10.0,
            ramp_seconds=5.0,
            active_seconds=5.0,
            recovery_seconds=5.0,
        )
        oracle = ControlledDynamicChannel(
            ControlledDynamicChannelConfig(
                seed=23,
                static_std_db=0.0,
                temporal_std_db=0.0,
                measurement_std_db=0.0,
                event=event,
            )
        )
        before = oracle.query_truth(
            elapsed_seconds=0.0,
            x_map=10.0,
            y_map=10.0,
            baseline_path_loss_db=100.0,
        )
        active = oracle.query_truth(
            elapsed_seconds=16.0,
            x_map=10.0,
            y_map=10.0,
            baseline_path_loss_db=100.0,
        )
        recovered = oracle.query_truth(
            elapsed_seconds=30.0,
            x_map=10.0,
            y_map=10.0,
            baseline_path_loss_db=100.0,
        )
        self.assertEqual(before.event_loss_db, 0.0)
        self.assertEqual(active.event_loss_db, 8.0)
        self.assertEqual(recovered.event_loss_db, 0.0)

    def test_measurement_noise_is_stable_per_observation_id(self) -> None:
        config = ControlledDynamicChannelConfig(
            seed=29,
            static_std_db=0.0,
            temporal_std_db=0.0,
            event=None,
        )
        first = ControlledDynamicChannel(config)
        second = ControlledDynamicChannel(config)
        a = first.sample_observation(
            observation_id="agent:1",
            elapsed_seconds=0.0,
            x_map=10.0,
            y_map=20.0,
            baseline_path_loss_db=90.0,
        )
        b = second.sample_observation(
            observation_id="agent:1",
            elapsed_seconds=0.0,
            x_map=10.0,
            y_map=20.0,
            baseline_path_loss_db=90.0,
        )
        self.assertEqual(a.measurement_noise_db, b.measurement_noise_db)
        self.assertTrue(math.isfinite(a.observed_path_loss_db))


if __name__ == "__main__":
    unittest.main()
