from __future__ import annotations

import os

# test environment: skip CKM building (hybrid-mode scenario construction no longer does a full grid scan)
os.environ.setdefault("RAN_DISABLE_CKM", "1")

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from ran.contracts import Position
from ran.radio.channel import estimate_channel
from ran.radio.channel_pipeline import evaluate_channel_path_loss
from ran.radio.channel_policy import (
    MODE_3GPP_PREFERRED,
    MODE_HYBRID,
    MODE_LEGACY,
    MODE_SHADOW,
    ChannelModelConfigError,
    load_channel_model_policy,
)
from ran.radio.topology_adapter import load_gnb_site_from_scene
from ran.scenario import RanUploadScenario
from structure.scene_registry import build_scene


class ChannelModelPolicyTests(unittest.TestCase):
    def test_bristol_runtime_presets_are_explicit(self) -> None:
        policy = load_channel_model_policy("bristol_topology")

        self.assertEqual(policy.mode, MODE_HYBRID)
        self.assertEqual(policy.gnb_heights["gnb_001"].height_m, 10.0)
        self.assertEqual(policy.gnb_heights["gnb_001"].status, "assumed")
        assert policy.default_ue_height is not None
        self.assertEqual(policy.default_ue_height.height_m, 1.5)
        self.assertEqual(
            policy.o2i_profiles["block_09_student_union"].penetration_model,
            "low_loss",
        )
        self.assertTrue(policy.allow_extrapolation_in_shadow)
        self.assertFalse(policy.allow_extrapolation_when_active)

    def test_unknown_scene_safely_uses_legacy(self) -> None:
        policy = load_channel_model_policy("not_configured")

        self.assertEqual(policy.mode, MODE_LEGACY)
        self.assertEqual(policy.gnb_heights, {})

    def test_invalid_mode_is_rejected(self) -> None:
        data = {
            "schema_version": "1",
            "scenes": {"test": {"mode": "mystery"}},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "channel_model.json"
            path.write_text(json.dumps(data), encoding="utf-8")

            with self.assertRaisesRegex(ChannelModelConfigError, "mode"):
                load_channel_model_policy("test", path)

    def test_unsupported_height_reference_is_rejected(self) -> None:
        data = {
            "schema_version": "1",
            "scenes": {"test": {"height_reference": "sea_level"}},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "channel_model.json"
            path.write_text(json.dumps(data), encoding="utf-8")

            with self.assertRaisesRegex(ChannelModelConfigError, "local_ground"):
                load_channel_model_policy("test", path)


class ChannelRuntimePipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.scene = build_scene("bristol_topology")
        cls.gnb = load_gnb_site_from_scene(cls.scene)
        cls.scenario = RanUploadScenario(cls.scene)

    def test_shadow_runs_full_o2i_chain_without_changing_selected_loss(self) -> None:
        policy = load_channel_model_policy("bristol_topology")
        legacy_loss = 130.05980565039312

        result = evaluate_channel_path_loss(
            scene=self.scene,
            receiver_position=self.scenario.ue_request.position,
            gnb=self.gnb,
            legacy_total_path_loss_db=legacy_loss,
            policy=policy,
        )

        # hybrid mode: the 3GPP evaluation value is the runtime value (legacy is no longer kept as the runtime value)
        self.assertEqual(result.selected_model, "3gpp_o2i")
        self.assertAlmostEqual(result.selected_total_path_loss_db, 108.5172986450)
        self.assertEqual(result.evaluated_model, "3gpp_o2i")
        self.assertAlmostEqual(result.evaluated_total_path_loss_db, 108.5172986450)
        self.assertTrue(result.is_extrapolated)
        assert result.geometry is not None
        self.assertAlmostEqual(result.geometry.distance.distance_2d_m, 75.3745854052)
        self.assertAlmostEqual(result.geometry.indoor_distance_m, 26.1181702916)
        self.assertAlmostEqual(result.external_wall_loss_db, 12.6975034595)
        self.assertAlmostEqual(result.indoor_loss_db, 13.0590851458)
        self.assertEqual(result.calibration_status, "provisional")
        self.assertEqual(result.bs_height_m, 10.0)
        self.assertEqual(result.bs_height_status, "assumed")
        self.assertEqual(result.ut_height_m, 1.5)
        self.assertEqual(result.penetration_model, "low_loss")

    def test_active_can_select_o2i_when_provisional_and_extrapolation_are_explicit(self) -> None:
        shadow_policy = load_channel_model_policy("bristol_topology")
        active_policy = replace(
            shadow_policy,
            mode=MODE_3GPP_PREFERRED,
            require_confirmed_calibration_when_active=False,
            allow_extrapolation_when_active=True,
        )

        result = evaluate_channel_path_loss(
            scene=self.scene,
            receiver_position=self.scenario.ue_request.position,
            gnb=self.gnb,
            legacy_total_path_loss_db=130.05980565039312,
            policy=active_policy,
        )

        self.assertEqual(result.selected_model, "3gpp_o2i")
        self.assertAlmostEqual(result.selected_total_path_loss_db, 108.5172986450)
        self.assertIsNone(result.fallback_reason)

    def test_active_default_rejects_provisional_calibration(self) -> None:
        shadow_policy = load_channel_model_policy("bristol_topology")
        active_policy = replace(shadow_policy, mode=MODE_3GPP_PREFERRED)

        result = evaluate_channel_path_loss(
            scene=self.scene,
            receiver_position=self.scenario.ue_request.position,
            gnb=self.gnb,
            legacy_total_path_loss_db=130.05980565039312,
            policy=active_policy,
        )

        self.assertEqual(result.selected_model, MODE_LEGACY)
        self.assertEqual(
            result.fallback_reason,
            "provisional_calibration_not_allowed_in_active_mode",
        )
        self.assertEqual(result.calibration_status, "provisional")

    def test_active_strict_rejects_default_ue_indoor_depth_over_25m(self) -> None:
        shadow_policy = load_channel_model_policy("bristol_topology")
        active_policy = replace(
            shadow_policy,
            mode=MODE_3GPP_PREFERRED,
            require_confirmed_calibration_when_active=False,
        )

        result = evaluate_channel_path_loss(
            scene=self.scene,
            receiver_position=self.scenario.ue_request.position,
            gnb=self.gnb,
            legacy_total_path_loss_db=130.05980565039312,
            policy=active_policy,
        )

        self.assertEqual(result.selected_model, MODE_LEGACY)
        self.assertIn("25 m", result.fallback_reason or "")
        self.assertIsNotNone(result.geometry)
        assert result.geometry is not None
        self.assertAlmostEqual(result.geometry.indoor_distance_m, 26.1181702916)

    def test_student_union_center_is_supported_without_extrapolation(self) -> None:
        shadow_policy = load_channel_model_policy("bristol_topology")
        active_policy = replace(
            shadow_policy,
            mode=MODE_3GPP_PREFERRED,
            require_confirmed_calibration_when_active=False,
        )

        result = evaluate_channel_path_loss(
            scene=self.scene,
            receiver_position=Position(517.5, 296.0),
            gnb=self.gnb,
            legacy_total_path_loss_db=999.0,
            policy=active_policy,
        )

        self.assertEqual(result.selected_model, "3gpp_o2i")
        self.assertFalse(result.is_extrapolated)
        self.assertIsNotNone(result.geometry)
        assert result.geometry is not None
        self.assertLessEqual(result.geometry.indoor_distance_m, 25.0)
        self.assertEqual(result.penetration_model, "low_loss")

    def test_estimate_channel_preserves_legacy_output_and_adds_shadow_metadata(self) -> None:
        channel = estimate_channel(
            tick=1,
            scene=self.scene,
            ue_request=self.scenario.ue_request,
            gnb=self.gnb,
        )

        # hybrid mode (pipeline fallback when CKM is unavailable): runtime value selects the 3GPP evaluation value
        self.assertEqual(channel.channel_model_mode, MODE_HYBRID)
        self.assertEqual(channel.path_loss_model, "3gpp_o2i")
        self.assertAlmostEqual(channel.total_path_loss_db, 108.5172986450)
        self.assertEqual(channel.evaluated_path_loss_model, "3gpp_o2i")
        self.assertAlmostEqual(channel.evaluated_total_path_loss_db, 108.5172986450)
        self.assertEqual(channel.link_type, "outdoor_to_indoor")
        self.assertAlmostEqual(channel.distance_2d_m, 75.3745854052)
        self.assertTrue(channel.is_extrapolated)
        self.assertGreater(len(channel.path_loss_warnings), 0)
        self.assertEqual(channel.calibration_id, "bristol_topology_uniform_extent_v1")
        self.assertEqual(channel.bs_height_source, "3gpp_umi_reference")
        self.assertEqual(channel.ut_height_source, "3gpp_umi_reference_handheld")


if __name__ == "__main__":
    unittest.main()
