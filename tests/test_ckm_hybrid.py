"""混合 CKM + Beamforming 单元测试:校准、残差、Beam、CKM 构建/查询/缓存。"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from ran.ckm.beam import BeamConfig, beam_gain_db, default_codebook, select_best_beam
from ran.ckm.calibration import apply_calibration, feature_vector, fit_calibration
from ran.ckm.ckm import HybridCkm, HybridCKMCell, compute_version_key
from ran.ckm.residual import IdwResidualModel, ResidualPoint
from ran.radio.channel_policy import MODE_HYBRID, load_channel_model_policy
from ran.radio.topology_adapter import load_gnb_site_from_scene
from structure.scene_registry import build_scene


class CalibrationTests(unittest.TestCase):
    def test_recovers_known_coefficients(self) -> None:
        # 手工构造:y = 2 + 3·brick + 1.5·glass - 0.5·nlos
        rows = []
        y = []
        # 正交特征(避免共线性吸收系数)
        for i in range(20):
            brick = float(i % 3)
            glass = float((i // 3) % 3)
            drywall = float(i % 2)
            exterior = float((i // 5) % 2)
            indoor = float(i % 5)
            nlos = 1.0 if i >= 10 else 0.0
            rows.append([1.0, brick, glass, drywall, exterior, indoor, nlos])
            y.append(2.0 + 3.0 * brick + 1.5 * glass - 0.2 * drywall + 0.5 * exterior - 0.5 * nlos)
        params = fit_calibration(feature_rows=rows, residual_db=y, ridge_lambda=0.0)
        self.assertAlmostEqual(params.intercept_db, 2.0, places=4)
        self.assertAlmostEqual(params.material_coefficients["brick"], 3.0, places=4)
        self.assertAlmostEqual(params.material_coefficients["glass"], 1.5, places=4)
        self.assertAlmostEqual(params.nlos_bias_db, -0.5, places=4)
        self.assertLess(params.calibration_rmse_db, 1e-6)

    def test_ridge_stabilizes_small_samples(self) -> None:
        # 7 特征(与 FEATURE_NAMES 对齐);小样本下 Ridge 仍产出有限系数
        rows = [[1.0, float(i), 0.0, 0.0, 0.0, 0.0, 0.0] for i in range(3)]
        y = [1.0, 2.0, 3.0]
        params = fit_calibration(feature_rows=rows, residual_db=y, ridge_lambda=0.1)
        self.assertTrue(abs(params.intercept_db) < 10.0)

    def test_apply_calibration(self) -> None:
        rows = [[1.0, 2.0, 0.0, 0.0, 0.0, 5.0, 1.0]]
        y = [3.0]
        params = fit_calibration(feature_rows=rows, residual_db=y, ridge_lambda=0.0)
        correction = apply_calibration(params, rows[0])
        self.assertAlmostEqual(correction, 3.0, places=4)


class ResidualTests(unittest.TestCase):
    def test_idw_exact_at_reference_point(self) -> None:
        model = IdwResidualModel(
            [ResidualPoint(0.0, 0.0, 2.0), ResidualPoint(10.0, 0.0, -1.0)],
            power=2.0,
            max_neighbors=8,
            prior_std_db=6.0,
        )
        pred = model.predict(0.0, 0.0)
        self.assertAlmostEqual(pred.residual_mean_db, 2.0, places=6)
        self.assertEqual(pred.supporting_measurement_count, 2)

    def test_uncertainty_grows_with_distance(self) -> None:
        model = IdwResidualModel(
            [ResidualPoint(0.0, 0.0, 0.0)],
            power=2.0,
            max_neighbors=8,
            prior_std_db=6.0,
            reference_distance_m=50.0,
        )
        near = model.predict(5.0, 0.0)
        far = model.predict(100.0, 0.0)
        self.assertGreater(far.residual_std_db, near.residual_std_db)

    def test_empty_model_falls_back_to_prior(self) -> None:
        model = IdwResidualModel([], prior_std_db=6.0)
        pred = model.predict(1.0, 1.0)
        self.assertEqual(pred.residual_mean_db, 0.0)
        self.assertEqual(pred.residual_std_db, 6.0)
        self.assertEqual(pred.supporting_measurement_count, 0)


class BeamTests(unittest.TestCase):
    def test_beam_gain_peaks_at_boresight(self) -> None:
        beam = BeamConfig(beam_id="b0", azimuth_deg=0.0, beamwidth_deg=45.0, max_gain_dbi=12.0)
        self.assertAlmostEqual(beam_gain_db(beam, 0.0), 12.0, places=6)
        off = beam_gain_db(beam, 45.0)
        self.assertAlmostEqual(off, 0.0, places=4)  # 12 - 12×(45/45)²
        far = beam_gain_db(beam, 180.0)
        self.assertAlmostEqual(far, 12.0 - 25.0, places=4)  # side lobe cap

    def test_select_best_beam_chooses_aligned_beam(self) -> None:
        gnb = load_gnb_site_from_scene(build_scene("bristol_topology"))
        codebook = default_codebook()
        # UE 在 gNB 正东(0° 方位)
        selection = select_best_beam(
            gnb=gnb,
            ue_x=gnb.position.x + 100.0,
            ue_y=gnb.position.y,
            los_state="los",
            codebook=codebook,
            nlos_gain_cap_db=-3.0,
            tx_power_dbm=46.0,
            path_loss_db=100.0,
        )
        assert selection is not None
        self.assertEqual(selection.beam_id, "b0")  # 0° 波束
        self.assertGreater(selection.beam_gain_db, 10.0)

    def test_nlos_gain_capped(self) -> None:
        gnb = load_gnb_site_from_scene(build_scene("bristol_topology"))
        los = select_best_beam(
            gnb=gnb,
            ue_x=gnb.position.x + 100.0,
            ue_y=gnb.position.y,
            los_state="los",
            codebook=default_codebook(),
            nlos_gain_cap_db=-3.0,
            tx_power_dbm=46.0,
            path_loss_db=100.0,
        )
        nlos = select_best_beam(
            gnb=gnb,
            ue_x=gnb.position.x + 100.0,
            ue_y=gnb.position.y,
            los_state="nlos",
            codebook=default_codebook(),
            nlos_gain_cap_db=-3.0,
            tx_power_dbm=46.0,
            path_loss_db=100.0,
        )
        assert los is not None and nlos is not None
        self.assertLessEqual(nlos.beam_gain_db, -3.0)
        self.assertGreater(los.beam_gain_db, nlos.beam_gain_db)


class CkmTests(unittest.TestCase):
    def test_version_key_changes_with_config(self) -> None:
        gnb = load_gnb_site_from_scene(build_scene("bristol_topology"))
        k1 = compute_version_key(scene_id="bristol_topology", gnb=gnb, calibration_version="v1", reference_count=20, seed=42)
        k2 = compute_version_key(scene_id="bristol_topology", gnb=gnb, calibration_version="v1", reference_count=40, seed=42)
        self.assertNotEqual(k1, k2)

    def test_ckm_build_query_and_cache_roundtrip(self) -> None:
        scene = build_scene("bristol_topology")
        gnb = load_gnb_site_from_scene(scene)
        policy = load_channel_model_policy("bristol_topology")
        self.assertEqual(policy.mode, MODE_HYBRID)

        from ran.ckm import CkmConfig, build_hybrid_ckm

        config = CkmConfig(
            grid_scale_m=200.0,
            indoor_refine_scale_m=100.0,
            cache_enabled=False,
            reference_count=5,
            reference_seed=7,
            target_build_seconds=60.0,
        )
        ckm = build_hybrid_ckm(scene=scene, gnb=gnb, policy=policy, ckm_config=config)
        self.assertIsNotNone(ckm)
        assert ckm is not None
        self.assertGreater(len(ckm.cells), 10)
        cell = ckm.query(gnb.position.x + 50.0, gnb.position.y + 50.0)
        self.assertIsNotNone(cell)
        assert cell is not None
        self.assertGreater(cell.hybrid_path_loss_db, 0.0)
        self.assertGreater(cell.prediction_std_db, 0.0)

        # 缓存往返(临时目录)
        with tempfile.TemporaryDirectory() as directory:
            from ran.ckm.ckm import cache_path
            import json as _json

            path = Path(directory) / "cache.json"
            path.write_text(_json.dumps(ckm.to_json()), encoding="utf-8")
            loaded = HybridCkm.from_json(_json.loads(path.read_text(encoding="utf-8")))
            self.assertEqual(loaded.version_key, ckm.version_key)
            self.assertEqual(len(loaded.cells), len(ckm.cells))
            same = loaded.query(gnb.position.x + 50.0, gnb.position.y + 50.0)
            self.assertIsNotNone(same)

    def test_ckm_disable_returns_none(self) -> None:
        scene = build_scene("bristol_topology")
        gnb = load_gnb_site_from_scene(scene)
        policy = load_channel_model_policy("bristol_topology")
        from ran.ckm import CkmConfig, build_hybrid_ckm

        ckm = build_hybrid_ckm(scene=scene, gnb=gnb, policy=policy, ckm_config=CkmConfig(enabled=False))
        self.assertIsNone(ckm)


if __name__ == "__main__":
    unittest.main()
