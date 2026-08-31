"""Repeat the controlled spatiotemporal CKM experiment across truth seeds.

The runner remains experiment-only.  It retains per-tick records so the
companion plotting script can show temporal behaviour rather than only final
aggregate bars or tables.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import statistics

from experiments.ckm_spatiotemporal_ablation import build_bristol_ablation


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "outputs" / "ckm_spatiotemporal_multiseed.json"
DEFAULT_SEEDS = (9042, 9043, 9044, 9045, 9046)

SCOPES = (
    "all_tracking_ticks",
    "spatial_holdout",
    "event_active",
    "non_event",
    "probe_agent",
    "frozen_forecast",
)
MODELS = ("physical", "static_ckm", "online_tracking", "frozen_forecast")


def aggregate_reports(reports: list[dict]) -> dict:
    """Aggregate seed-level metrics without pooling ticks across seeds."""

    if not reports:
        raise ValueError("at least one report is required")
    aggregate: dict[str, dict] = {}
    for scope in SCOPES:
        aggregate[scope] = {}
        for model in MODELS:
            available = [
                report["summary"][scope][model]
                for report in reports
                if model in report["summary"][scope]
            ]
            if not available:
                continue
            aggregate[scope][model] = {
                metric: _mean_std([float(values[metric]) for values in available])
                for metric in ("mae_db", "rmse_db", "bias_db")
            }

        static_rmse = [
            float(report["summary"][scope]["static_ckm"]["rmse_db"])
            for report in reports
        ]
        online_key = "frozen_forecast" if scope == "frozen_forecast" else "online_tracking"
        online_rmse = [
            float(report["summary"][scope][online_key]["rmse_db"])
            for report in reports
        ]
        improvements = [
            100.0 * (static - online) / static
            for static, online in zip(static_rmse, online_rmse)
            if static > 0.0
        ]
        aggregate[scope]["relative_rmse_improvement_percent"] = _mean_std(improvements)

    coverage = [
        float(
            report["summary"]["all_tracking_ticks"]["online_tracking"][
                "prediction_interval_90_coverage"
            ]
        )
        for report in reports
    ]
    prediction_median = [
        float(report["runtime"]["prediction_latency_ms"]["median"])
        for report in reports
    ]
    update_median = [
        float(report["runtime"]["observation_latency_ms"]["median"])
        for report in reports
    ]
    return {
        "seed_count": len(reports),
        "scopes": aggregate,
        "prediction_interval_90_coverage": _mean_std(coverage),
        "prediction_latency_median_ms": _mean_std(prediction_median),
        "observation_latency_median_ms": _mean_std(update_median),
    }


def _mean_std(values: list[float]) -> dict[str, float]:
    if not values or any(not math.isfinite(value) for value in values):
        raise ValueError("aggregate values must be finite and non-empty")
    return {
        "mean": statistics.fmean(values),
        "std": statistics.stdev(values) if len(values) > 1 else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-seed controlled CKM evaluation.")
    parser.add_argument("--seeds", type=int, nargs="+", default=list(DEFAULT_SEEDS))
    parser.add_argument("--ticks", type=int, default=120)
    parser.add_argument("--tick-ms", type=float, default=1000.0)
    parser.add_argument("--forecast-train-ticks", type=int)
    parser.add_argument("--grid", type=float, default=100.0)
    parser.add_argument("--indoor-grid", type=float, default=50.0)
    parser.add_argument("--agent-speed", type=float, default=15.0)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    reports = []
    for index, seed in enumerate(args.seeds, start=1):
        print(f"[ckm-multiseed] running seed {seed} ({index}/{len(args.seeds)})", flush=True)
        reports.append(
            build_bristol_ablation(
                ticks=args.ticks,
                tick_ms=args.tick_ms,
                forecast_train_ticks=args.forecast_train_ticks,
                grid_scale_m=args.grid,
                indoor_refine_scale_m=args.indoor_grid,
                agent_speed_map_units_per_tick=args.agent_speed,
                truth_seed=seed,
                include_records=True,
            )
        )

    payload = {
        "experiment": "physics_informed_online_spatiotemporal_ckm_multiseed",
        "scope": "controlled_simulation_only",
        "seeds": list(args.seeds),
        "aggregate": aggregate_reports(reports),
        "reports": reports,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(payload["aggregate"], ensure_ascii=False, indent=2))
    print(f"report: {args.output}")


if __name__ == "__main__":
    main()
