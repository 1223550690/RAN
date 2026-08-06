"""CKM pre-generation script: when the scene is unchanged, build once offline and
the simulation loads the cache directly at startup.

Usage:
    python -m ran.ckm.pregen --scene bristol_topology [--grid 10 --indoor 5]

Output: outputs/ckm_cache_{scene_id}.json (the version key binds scene / gNB /
frequency / power / calibration / reference / codebook; any change triggers an
automatic rebuild).
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
        print(f"[ckm-pregen] channel_model.json mode for scene {args.scene} is not hybrid; no pre-generation needed.", file=sys.stderr)
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
        print("[ckm-pregen] build failed (returned None).", file=sys.stderr)
        sys.exit(1)
    print(
        f"[ckm-pregen] done: cells={len(ckm.cells)} refs={ckm.model_metadata.get('reference_count')} "
        f"elapsed={time.time() - t0:.1f}s version={ckm.version_key}"
    )
    from ran.ckm.ckm import cache_path

    print(f"[ckm-pregen] cache: {cache_path(args.scene)}")


if __name__ == "__main__":
    main()
