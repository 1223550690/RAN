"""CKM 预生成脚本:场景不变时离线构建一次,模拟启动直接加载缓存。

用法:
    python -m ran.ckm.pregen --scene bristol_topology [--grid 10 --indoor 5]

输出:outputs/ckm_cache_{scene_id}.json(版本键绑定场景/gNB/频率/功率/校准/参考/码本;
任一变化自动重建)。
"""
from __future__ import annotations

import argparse
import sys
import time


def main() -> None:
    parser = argparse.ArgumentParser(description="Pre-generate the hybrid CKM cache for a scene.")
    parser.add_argument("--scene", default="bristol_topology")
    parser.add_argument("--grid", type=float, default=10.0, help="outdoor grid scale in meters")
    parser.add_argument("--indoor", type=float, default=5.0, help="indoor refine grid scale in meters")
    parser.add_argument("--ref-count", type=int, default=20, help="synthetic reference sample count")
    parser.add_argument("--ref-seed", type=int, default=42)
    parser.add_argument("--target-seconds", type=float, default=30.0, help="build time budget")
    args = parser.parse_args()

    from ran.ckm import CkmConfig, build_hybrid_ckm
    from ran.radio.channel_policy import load_channel_model_policy
    from ran.radio.topology_adapter import load_gnb_site_from_scene
    from structure.scene_registry import build_scene

    scene = build_scene(args.scene)
    gnb = load_gnb_site_from_scene(scene)
    policy = load_channel_model_policy(str(getattr(scene, "node_id", args.scene)))
    if not getattr(policy, "is_hybrid", False):
        print(f"[ckm-pregen] 场景 {args.scene} 的 channel_model.json mode 不是 hybrid,无需预生成。", file=sys.stderr)
        sys.exit(1)

    config = CkmConfig(
        grid_scale_m=args.grid,
        indoor_refine_scale_m=args.indoor,
        cache_enabled=True,
        reference_count=args.ref_count,
        reference_seed=args.ref_seed,
        target_build_seconds=args.target_seconds,
    )
    t0 = time.time()
    ckm = build_hybrid_ckm(scene=scene, gnb=gnb, policy=policy, ckm_config=config)
    if ckm is None:
        print("[ckm-pregen] 构建失败(返回 None)。", file=sys.stderr)
        sys.exit(1)
    print(
        f"[ckm-pregen] 完成: cells={len(ckm.cells)} refs={ckm.model_metadata.get('reference_count')} "
        f"耗时={time.time() - t0:.1f}s 版本={ckm.version_key}"
    )
    from ran.ckm.ckm import cache_path

    print(f"[ckm-pregen] 缓存: {cache_path(args.scene)}")


if __name__ == "__main__":
    main()
