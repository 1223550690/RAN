"""混合 CKM 构建器(环节四~八组装):启动时一次生成,缓存复用。"""
from __future__ import annotations

import hashlib
import math
import time
from dataclasses import dataclass, field

from ran.ckm.beam import BeamConfig, default_codebook, select_best_beam
from ran.ckm.calibration import apply_calibration, feature_vector, fit_calibration
from ran.ckm.ckm import (
    HybridCkm,
    HybridCKMCell,
    cache_path,
    compute_version_key,
    scene_structure_hash,
)
from ran.ckm.reference import build_reference_measurements
from ran.ckm.residual import GaussianProcessResidualModel, IdwResidualModel, ResidualPoint
from ran.radio.channel_pipeline import evaluate_channel_path_loss
from ran.radio.geometry import PropagationGeometry, analyze_propagation_geometry, coordinate_view_from_calibration


@dataclass(slots=True)
class CkmConfig:
    """channel_model.json 中 scenes.<id>.ckm 配置。"""

    enabled: bool = True
    grid_scale_m: float = 10.0
    indoor_refine_scale_m: float = 5.0
    cache_enabled: bool = True
    reference_count: int = 20
    reference_seed: int = 42
    ridge_lambda: float = 0.1
    residual_power: float = 2.0
    residual_max_neighbors: int = 8
    residual_prior_std_db: float = 6.0
    residual_reference_distance_m: float = 50.0
    residual_method: str = "gp"  # residual_method: "gp"(Matérn 3/2 Kriging,默认)/ "idw"。
    residual_length_scale_m: float = 50.0
    residual_signal_std_db: float = 6.0
    residual_noise_std_db: float = 1.0
    beam_enabled: bool = True
    beam_codebook: list[BeamConfig] = field(default_factory=default_codebook)
    nlos_gain_cap_db: float | None = -3.0
    target_build_seconds: float = 15.0  # 性能预算;超时自动降级粗网格

    @staticmethod
    def from_dict(data: dict | None) -> "CkmConfig":
        if not data:
            return CkmConfig()
        beam_data = data.get("beam") or {}
        codebook = [
            BeamConfig(
                beam_id=str(b.get("beam_id")),
                azimuth_deg=float(b.get("azimuth_deg", 0.0)),
                beamwidth_deg=float(b.get("beamwidth_deg", 45.0)),
                max_gain_dbi=float(b.get("max_gain_dbi", 12.0)),
                side_lobe_level_db=float(b.get("side_lobe_level_db", 25.0)),
            )
            for b in beam_data.get("codebook", [])
        ]
        if not codebook:
            codebook = default_codebook()
        return CkmConfig(
            enabled=bool(data.get("enabled", True)),
            grid_scale_m=float(data.get("grid_scale_m", 10.0)),
            indoor_refine_scale_m=float(data.get("indoor_refine_scale_m", 5.0)),
            cache_enabled=bool(data.get("cache_enabled", True)),
            reference_count=int(data.get("reference", {}).get("count", 20)),
            reference_seed=int(data.get("reference", {}).get("seed", 42)),
            ridge_lambda=float(data.get("calibration", {}).get("ridge_lambda", 0.1)),
            residual_power=float(data.get("residual", {}).get("power", 2.0)),
            residual_max_neighbors=int(data.get("residual", {}).get("max_neighbors", 8)),
            residual_prior_std_db=float(data.get("residual", {}).get("prior_std_db", 6.0)),
            residual_reference_distance_m=float(data.get("residual", {}).get("reference_distance_m", 50.0)),
            residual_method=str(data.get("residual", {}).get("method", "gp")),
            residual_length_scale_m=float(data.get("residual", {}).get("length_scale_m", 50.0)),
            residual_signal_std_db=float(data.get("residual", {}).get("signal_std_db", 6.0)),
            residual_noise_std_db=float(data.get("residual", {}).get("noise_std_db", 1.0)),
            beam_enabled=bool(beam_data.get("enabled", True)),
            beam_codebook=codebook,
            nlos_gain_cap_db=(
                float(beam_data["nlos_gain_cap_db"]) if beam_data.get("nlos_gain_cap_db") is not None else None
            ),
            target_build_seconds=float(data.get("target_build_seconds", 15.0)),
        )


def _building_bounds(scene) -> list[tuple[float, float, float, float]]:
    """顶层 indoor 建筑区域 bounds(全局坐标)。

    只保留 metadata.space == indoor 的区域——绿地/球场/网络站点等
    outdoor 区域不是建筑,不能进"室内细网格"(曾导致户外点被当作
    indoor 采样,receiver_space 与实际传播几何矛盾)。
    """

    bounds = []
    for area in getattr(scene, "areas", []):
        meta = getattr(area, "metadata", {}) or {}
        if str(meta.get("space", "")).lower() != "indoor":
            continue
        b = getattr(area, "bounds", None)
        if b is None:
            continue
        if len(b) >= 4:
            bounds.append((float(b[0]), float(b[1]), float(b[2]), float(b[3])))
    return bounds


def _sample_grid_points(
    scene,
    *,
    grid_scale_m: float,
    indoor_refine_scale_m: float,
) -> list[dict]:
    """双层采样:户外粗网格 + 建筑内细网格。返回 [{"x": .., "y": .., "indoor": bool}]。"""

    bounds = _building_bounds(scene)
    if not bounds:
        return []
    xs0 = min(b[0] for b in bounds)
    ys0 = min(b[1] for b in bounds)
    xs1 = max(b[2] for b in bounds)
    ys1 = max(b[3] for b in bounds)
    margin = grid_scale_m * 2
    points: list[dict] = []

    def in_building(x: float, y: float) -> bool:
        # 半开区间:右/上边界点算户外(避免 bounds 边界带出现覆盖空洞:
        # 户外点被当室内跳过、室内网格又到不了边界 → 25m 降采样空洞)
        return any(b[0] <= x < b[2] and b[1] <= y < b[3] for b in bounds)

    # 户外粗网格(跳过建筑内部);从地图原点 0 覆盖到 2000(viewBox 边界),
    # 保证全图无白条(此前范围止于 bounds±margin,左上与右/下边缘缺失)。
    map_extent = 2000.0
    x = 0.0
    while x <= map_extent:
        y = 0.0
        while y <= map_extent:
            if not in_building(x, y):
                points.append({"x": x, "y": y, "indoor": False})
            y += grid_scale_m
        x += grid_scale_m

    # 室内细网格(建筑 bounds 内)
    for bx0, by0, bx1, by1 in bounds:
        x = bx0
        while x <= bx1:
            y = by0
            while y <= by1:
                points.append({"x": x, "y": y, "indoor": True})
                y += indoor_refine_scale_m
            x += indoor_refine_scale_m
    return points


def _compute_point_batch(payload):
    """并行 worker:计算一批网格点的几何 + 3GPP 物理先验(Windows spawn 可 pickle)。"""

    scene, gnb, policy, coordinate_view, points = payload
    import math

    from ran.contracts import Position
    from ran.radio.channel_pipeline import evaluate_channel_path_loss
    from ran.radio.geometry import analyze_propagation_geometry
    from services.map_service import MapService

    map_service = MapService()
    results = []
    for x, y, indoor in points:
        geometry = analyze_propagation_geometry(
            scene=scene,
            receiver_position=Position(x=x, y=y),
            gnb=gnb,
            coordinate_view=coordinate_view,
            map_service=map_service,
        )
        legacy_pl = (
            32.4
            + 20.0 * math.log10(gnb.carrier_freq_mhz)
            + 20.0 * math.log10(max(math.hypot(x - gnb.position.x, y - gnb.position.y), 1.0) / 1000.0)
        )
        evaluation = evaluate_channel_path_loss(
            scene=scene,
            receiver_position=Position(x=x, y=y),
            gnb=gnb,
            legacy_total_path_loss_db=legacy_pl,
            policy=policy,
            geometry=geometry,
        )
        results.append(
            {
                "x": x,
                "y": y,
                "indoor": indoor,
                "geometry": geometry,
                "path_loss_db": evaluation.selected_total_path_loss_db,
                "shadow_std_db": evaluation.shadow_fading_std_db,
            }
        )
    return results


def _write_heatmap(ckm: HybridCkm, scene_id: str, scale_m: float = 25.0, output_dir=None) -> None:
    """写轻量热力图文件(25m 降采样,前端叠加用;室内细网格优先)。

    坐标输出标准网格原点(key×scale,非覆盖点的原始采样坐标)——保证
    相邻色块连续铺设(点间距恒等于 scale,前端按固定尺寸绘制无缝)。
    """

    grid: dict[tuple[int, int], HybridCKMCell] = {}
    for cell in ckm.cells:
        key = (round(cell.x_map / scale_m), round(cell.y_map / scale_m))
        # 后写覆盖:cells 顺序户外先、室内后 → 室内点优先
        grid[key] = cell
    points = [
        {
            "x": float(key[0] * scale_m),
            "y": float(key[1] * scale_m),
            "rsrp": round(cell.predicted_rsrp_dbm, 2),
        }
        for key, cell in grid.items()
    ]
    try:
        import json

        from ran.ckm.ckm import CKM_CACHE_DIR

        path = (output_dir or CKM_CACHE_DIR) / f"ckm_heatmap_{scene_id}.json"
        path.write_text(json.dumps({"scene_id": scene_id, "grid_scale_m": scale_m, "points": points}), encoding="utf-8")
    except OSError:
        pass


def build_hybrid_ckm(
    *,
    scene,
    gnb,
    policy,
    ckm_config: CkmConfig | None = None,
    calibration_version: str = "ckm-v7",
) -> HybridCkm | None:
    """构建(或从缓存加载)混合 CKM;失败返回 None(调用方回退 shadow)。"""

    if ckm_config is None:
        ckm_config = CkmConfig()
    if not ckm_config.enabled:
        return None
    scene_id = str(getattr(scene, "node_id", ""))
    policy_hash = hashlib.sha256(str(sorted(policy.o2i_profiles.keys())).encode()).hexdigest()[:8]
    scene_hash = scene_structure_hash(scene)

    version_key = compute_version_key(
        scene_id=scene_id,
        gnb=gnb,
        calibration_version=calibration_version,
        reference_count=ckm_config.reference_count,
        seed=ckm_config.reference_seed,
        policy_hash=policy_hash,
        scene_hash=scene_hash,
    )
    # 缓存命中
    if ckm_config.cache_enabled:
        path = cache_path(scene_id)
        if path.exists():
            try:
                import json

                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("version_key") == version_key:
                    loaded = HybridCkm.from_json(data)
                    _write_heatmap(loaded, scene_id)
                    return loaded
            except (OSError, ValueError, KeyError, TypeError):
                pass

    t0 = time.time()
    # 坐标标定视图(几何分析需要米制距离)
    calibration = None
    from ran.radio.coordinate_calibration import load_coordinate_calibration

    calibration = load_coordinate_calibration(scene_id)
    coordinate_view = None
    gnb_height_m = 10.0
    ue_height_m = 1.5
    if calibration is not None:
        from ran.radio.channel_policy import HeightPreset

        gnb_height = policy.gnb_heights.get(gnb.gnb_id) or HeightPreset(height_m=10.0, source="default")
        ue_height = policy.default_ue_height or HeightPreset(height_m=1.5, source="default")
        gnb_height_m = gnb_height.height_m
        ue_height_m = ue_height.height_m
        coordinate_view = coordinate_view_from_calibration(
            calibration,
            gnb_height_m=gnb_height_m,
            ue_height_m=ue_height_m,
        )

    grid_scale = ckm_config.grid_scale_m
    indoor_scale = ckm_config.indoor_refine_scale_m
    raw_points = _sample_grid_points(scene, grid_scale_m=grid_scale, indoor_refine_scale_m=indoor_scale)
    if not raw_points:
        return None

    # 每点:几何 + 3GPP 物理先验(复用现有 pipeline,含 fallback 语义)。
    # 并行:ProcessPool(spawn)多 worker 分块计算;预算内提交尽可能多的块。
    candidate_points: list[dict] = []
    tx_power = gnb.tx_power_dbm
    antenna_gain = min(12.0, 10.0 * math.log10(max(1, gnb.antenna_elements)) * 0.5)
    timed_out = False
    from concurrent.futures import ProcessPoolExecutor

    chunk = 400
    batches = [
        (
            scene,
            gnb,
            policy,
            coordinate_view,
            [(p["x"], p["y"], p["indoor"]) for p in raw_points[i : i + chunk]],
        )
        for i in range(0, len(raw_points), chunk)
    ]
    n_workers = 8
    # 预算容量 = 目标秒数 × 并行吞吐(单点 ~1.2ms,每 worker ~800 点/s);
    # 默认配置(8 万点)可在预算内全量完成。
    budget_points = int(ckm_config.target_build_seconds * 800 * n_workers)
    with ProcessPoolExecutor(max_workers=n_workers) as pool:
        futures = []
        submitted = 0
        for batch in batches:
            if submitted >= budget_points:
                timed_out = True
                break
            futures.append(pool.submit(_compute_point_batch, batch))
            submitted += len(batch[4])
        for future in futures:
            try:
                candidate_points.extend(future.result())
            except Exception as exc:
                print(f"[ckm] 并行采样批次失败(跳过): {exc}", file=sys.stderr, flush=True)

    # 参考样本(分层)→ 校准
    references = build_reference_measurements(
        scene=scene,
        gnb=gnb,
        policy=policy,
        candidate_points=candidate_points,
        count=ckm_config.reference_count,
        seed=ckm_config.reference_seed,
        tx_power_dbm=tx_power,
    )
    feature_rows = []
    residual_vals = []
    residual_points: list[ResidualPoint] = []
    for ref in references:
        geom = next(p["geometry"] for p in candidate_points if abs(p["x"] - ref.receiver_x_map) < 1e-6 and abs(p["y"] - ref.receiver_y_map) < 1e-6)
        feature_rows.append(feature_vector(geom))
        residual_vals.append(ref.measured_path_loss_db - ref.physical_path_loss_db)
        residual_points.append(ResidualPoint(x_map=ref.receiver_x_map, y_map=ref.receiver_y_map, residual_db=residual_vals[-1]))
    calibration_params = fit_calibration(
        feature_rows=feature_rows,
        residual_db=residual_vals,
        ridge_lambda=ckm_config.ridge_lambda,
        model_version=calibration_version,
    )
    if ckm_config.residual_method == "idw":
        residual_model = IdwResidualModel(
            residual_points,
            power=ckm_config.residual_power,
            max_neighbors=ckm_config.residual_max_neighbors,
            prior_std_db=ckm_config.residual_prior_std_db,
            reference_distance_m=ckm_config.residual_reference_distance_m,
        )
    else:
        residual_model = GaussianProcessResidualModel(
            residual_points,
            length_scale_m=ckm_config.residual_length_scale_m,
            signal_std_db=ckm_config.residual_signal_std_db,
            noise_std_db=ckm_config.residual_noise_std_db,
            prior_std_db=ckm_config.residual_prior_std_db,
        )

    # cells 转换(快:IDW 残差 + 校准 + beam;候选点已采样完毕,转换不设时限)
    cells: list[HybridCKMCell] = []
    for point in candidate_points:
        geometry: PropagationGeometry = point["geometry"]
        pl_physical = float(point["path_loss_db"])
        features = feature_vector(geometry)
        calibration_db = apply_calibration(calibration_params, features)
        pl_calibrated = pl_physical + calibration_db
        residual = residual_model.predict(point["x"], point["y"])
        pl_hybrid = pl_calibrated + residual.residual_mean_db
        shadow_std = float(point.get("shadow_std_db") or 0.0)
        std = math.sqrt(shadow_std**2 + residual.residual_std_db**2)
        rsrp = tx_power + antenna_gain - pl_hybrid

        best_beam_id = None
        best_beam_rsrp = None
        beam_margin = None
        if ckm_config.beam_enabled:
            selection = select_best_beam(
                gnb=gnb,
                ue_x=point["x"],
                ue_y=point["y"],
                los_state=geometry.los_state,
                codebook=ckm_config.beam_codebook,
                nlos_gain_cap_db=ckm_config.nlos_gain_cap_db,
                tx_power_dbm=tx_power,
                path_loss_db=pl_hybrid,
            )
            if selection is not None:
                best_beam_id = selection.beam_id
                best_beam_rsrp = selection.effective_received_power_dbm
                beam_margin = selection.beam_margin_db

        # receiver_space 以传播几何的权威分类为准(采样标记只用于选择网格密度)
        receiver_space = str(getattr(geometry, "receiver_space", "") or "").lower()
        if receiver_space not in ("indoor", "outdoor"):
            receiver_space = "indoor" if point["indoor"] else "outdoor"
        cells.append(
            HybridCKMCell(
                grid_x=round(point["x"] / (indoor_scale if receiver_space == "indoor" else grid_scale)),
                grid_y=round(point["y"] / (indoor_scale if receiver_space == "indoor" else grid_scale)),
                x_map=point["x"],
                y_map=point["y"],
                receiver_space=receiver_space,
                receiver_building_id=geometry.receiver_building_id,
                link_type=geometry.link_type,
                los_state=geometry.los_state,
                distance_2d_m=geometry.distance.distance_2d_m or 0.0,
                distance_3d_m=geometry.distance.distance_3d_m or 0.0,
                outdoor_distance_m=geometry.outdoor_distance_m or 0.0,
                indoor_distance_m=geometry.indoor_distance_m or 0.0,
                exterior_walls_crossed=[c.surface_id for c in geometry.exterior_surfaces_crossed],
                interior_walls_crossed=[c.surface_id for c in geometry.interior_walls_crossed],
                portals_crossed=[c.portal_id for c in geometry.portals_crossed],
                physical_path_loss_db=pl_physical,
                calibrated_path_loss_db=pl_calibrated,
                residual_correction_db=residual.residual_mean_db,
                hybrid_path_loss_db=pl_hybrid,
                predicted_rsrp_dbm=rsrp,
                prediction_std_db=std,
                best_beam_id=best_beam_id,
                best_beam_rsrp_dbm=best_beam_rsrp,
                beam_margin_db=beam_margin,
                shadow_std_db=shadow_std,
            )
        )
        # 转换阶段不设时限(候选点已算完,这里只有轻量计算)
    
    ckm = HybridCkm(
        scene_id=scene_id,
        version_key=version_key,
        grid_scale_m=grid_scale,
        indoor_refine_scale_m=indoor_scale,
        cells=cells,
        model_metadata={
            "reference_count": len(references),
            "calibration_rmse_db": calibration_params.calibration_rmse_db,
            "cell_count": len(cells),
            "build_seconds": round(time.time() - t0, 2),
        },
    )
    ckm._building_bounds = _building_bounds(scene)

    if ckm_config.cache_enabled and ckm.cells:
        try:
            import json

            path = cache_path(scene_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(ckm.to_json(), ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
    _write_heatmap(ckm, scene_id)
    return ckm
