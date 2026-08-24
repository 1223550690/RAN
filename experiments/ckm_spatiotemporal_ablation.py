"""Bristol spatiotemporal CKM ablation with strict oracle/estimator separation.

The experiment reuses the current static Hybrid CKM and deterministic Agent
definitions, but it does not start the RAN runtime.  At every tick it scores
predictions before sparse measurement-Agent observations are assimilated.

Example:
    python -m experiments.ckm_spatiotemporal_ablation --ticks 120 --pretty
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path
import statistics
import tempfile
import time

from experiments.controlled_dynamic_channel import (
    ControlledDynamicChannel,
    ControlledDynamicChannelConfig,
    ControlledEventConfig,
)
from ran.ckm import CkmConfig, build_hybrid_ckm
from ran.ckm.online_spatiotemporal import (
    CkmObservation,
    OnlineSpatiotemporalConfig,
    OnlineSpatiotemporalResidualModel,
)
from ran.radio.channel_policy import load_channel_model_policy
from ran.radio.topology_adapter import load_gnb_site_from_scene
from simulation.agent.definitions import load_agent_simulation_definition
from simulation.agent.navigation import NavigationPlanner
from structure.scene_registry import build_scene


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AGENT_CONFIG = PROJECT_ROOT / "configs" / "agents" / "deterministic_three_agents_bristol.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "outputs" / "ckm_spatiotemporal_ablation.json"


def build_bristol_ablation(
    *,
    ticks: int = 120,
    tick_ms: float = 1000.0,
    forecast_train_ticks: int | None = None,
    grid_scale_m: float = 100.0,
    indoor_refine_scale_m: float = 50.0,
    agent_speed_map_units_per_tick: float = 15.0,
    truth_seed: int = 9042,
) -> dict:
    """Run the controlled experiment and return a JSON-serialisable report."""

    if ticks < 4:
        raise ValueError("ticks must be at least 4")
    if not math.isfinite(tick_ms) or tick_ms <= 0.0:
        raise ValueError("tick_ms must be positive and finite")
    if not math.isfinite(agent_speed_map_units_per_tick) or agent_speed_map_units_per_tick <= 0.0:
        raise ValueError("agent speed must be positive and finite")
    train_ticks = forecast_train_ticks if forecast_train_ticks is not None else ticks // 2
    if train_ticks <= 0 or train_ticks >= ticks:
        raise ValueError("forecast_train_ticks must be between 1 and ticks-1")

    scene = build_scene("bristol_topology")
    gnb = load_gnb_site_from_scene(scene)
    policy = load_channel_model_policy("bristol_topology")
    # build_hybrid_ckm() currently writes a preview heatmap even when caching is
    # disabled.  Redirect that generated side effect so this isolated
    # experiment cannot overwrite the main preview/report heatmap.
    from ran.ckm import ckm as ckm_module

    original_output_dir = ckm_module.CKM_CACHE_DIR
    with tempfile.TemporaryDirectory(prefix="ckm-spatiotemporal-") as directory:
        ckm_module.CKM_CACHE_DIR = Path(directory)
        try:
            static_ckm = build_hybrid_ckm(
                scene=scene,
                gnb=gnb,
                policy=policy,
                ckm_config=CkmConfig(
                    grid_scale_m=grid_scale_m,
                    indoor_refine_scale_m=indoor_refine_scale_m,
                    cache_enabled=False,
                    reference_count=20,
                    reference_seed=42,
                    target_build_seconds=60.0,
                ),
            )
        finally:
            ckm_module.CKM_CACHE_DIR = original_output_dir
    if static_ckm is None:
        raise RuntimeError("static Hybrid CKM could not be built")

    trajectories = _build_agent_trajectories(
        scene=scene,
        ticks=ticks,
        speed_map_units_per_tick=agent_speed_map_units_per_tick,
    )
    # Preserve the deterministic definition order: student + teacher provide
    # sparse observations, while staff remains an unseen probe Agent.
    agent_ids = list(trajectories)
    if len(agent_ids) < 2:
        raise RuntimeError("at least two Agent trajectories are required")
    measurement_agent_ids = set(agent_ids[:-1])
    probe_agent_ids = set(agent_ids[-1:])

    bounds = (0.0, 0.0, 2000.0, 2000.0)
    estimator_config = OnlineSpatiotemporalConfig(
        scene_bounds=bounds,
        basis_columns=5,
        basis_rows=5,
        time_constant_seconds=45.0,
        prior_std_db=6.0,
        measurement_std_db=1.5,
        model_discrepancy_std_db=1.5,
        max_correction_db=15.0,
        support_radius_map_units=240.0,
        support_time_constant_seconds=50.0,
    )
    tracking_model = OnlineSpatiotemporalResidualModel(
        scene_id="bristol_topology",
        gnb_id=gnb.gnb_id,
        carrier_freq_mhz=gnb.carrier_freq_mhz,
        config=estimator_config,
    )
    forecast_model = OnlineSpatiotemporalResidualModel(
        scene_id="bristol_topology",
        gnb_id=gnb.gnb_id,
        carrier_freq_mhz=gnb.carrier_freq_mhz,
        config=estimator_config,
    )
    event = ControlledEventConfig(
        center_x_map=1050.0,
        center_y_map=950.0,
        radius_map_units=220.0,
        max_loss_db=8.0,
        start_seconds=ticks * tick_ms / 1000.0 * 0.25,
        ramp_seconds=max(tick_ms / 1000.0, ticks * tick_ms / 1000.0 * 0.08),
        active_seconds=ticks * tick_ms / 1000.0 * 0.30,
        recovery_seconds=ticks * tick_ms / 1000.0 * 0.15,
    )
    oracle = ControlledDynamicChannel(
        ControlledDynamicChannelConfig(
            seed=truth_seed,
            static_std_db=2.5,
            temporal_std_db=3.0,
            measurement_std_db=1.0,
            coherence_time_seconds=35.0,
            event=event,
        )
    )

    holdout_points = {
        "holdout_event_center": (event.center_x_map, event.center_y_map),
        "holdout_northwest": (350.0, 1550.0),
        "holdout_southeast": (1600.0, 450.0),
    }
    records: list[dict] = []
    prediction_durations_ms: list[float] = []
    observation_durations_ms: list[float] = []
    accepted_updates = 0

    for tick in range(ticks):
        elapsed_seconds = tick * tick_ms / 1000.0
        oracle.advance_to(elapsed_seconds)
        points: list[tuple[str, str, float, float]] = []
        for agent_id in agent_ids:
            x_map, y_map = trajectories[agent_id][tick]
            scope = "measurement_agent" if agent_id in measurement_agent_ids else "probe_agent"
            points.append((scope, agent_id, x_map, y_map))
        for point_id, (x_map, y_map) in holdout_points.items():
            points.append(("spatial_holdout", point_id, x_map, y_map))

        point_context: dict[str, tuple[float, float, float, float]] = {}
        for scope, point_id, x_map, y_map in points:
            cell = static_ckm.query(x_map, y_map)
            if cell is None:
                continue
            static_path_loss = cell.hybrid_path_loss_db
            physical_path_loss = cell.physical_path_loss_db
            truth = oracle.query_truth(
                elapsed_seconds=elapsed_seconds,
                x_map=x_map,
                y_map=y_map,
                baseline_path_loss_db=static_path_loss,
            )

            started = time.perf_counter()
            tracking = tracking_model.predict_at(
                elapsed_seconds=elapsed_seconds,
                x_map=x_map,
                y_map=y_map,
                baseline_path_loss_db=static_path_loss,
            )
            forecast = forecast_model.predict_at(
                elapsed_seconds=elapsed_seconds,
                x_map=x_map,
                y_map=y_map,
                baseline_path_loss_db=static_path_loss,
            )
            prediction_durations_ms.append((time.perf_counter() - started) * 1000.0 / 2.0)

            tracking_error = tracking.selected_path_loss_db - truth.truth_path_loss_db
            forecast_error = forecast.selected_path_loss_db - truth.truth_path_loss_db
            records.append(
                {
                    "tick": tick,
                    "elapsed_seconds": elapsed_seconds,
                    "scope": scope,
                    "point_id": point_id,
                    "event_loss_db": truth.event_loss_db,
                    "physical_error_db": physical_path_loss - truth.truth_path_loss_db,
                    "static_error_db": static_path_loss - truth.truth_path_loss_db,
                    "tracking_error_db": tracking_error,
                    "forecast_error_db": forecast_error,
                    "tracking_std_db": tracking.residual_std_db,
                    "tracking_accepted": tracking.accepted,
                    "tracking_support_score": tracking.support_score,
                    "forecast_accepted": forecast.accepted,
                    "tracking_90_covered": (
                        abs(tracking_error) <= 1.6448536269514722 * tracking.residual_std_db
                    ),
                }
            )
            point_context[point_id] = (
                x_map,
                y_map,
                static_path_loss,
                truth.truth_path_loss_db,
            )

        # Strict prequential order: all points were scored before observations.
        for agent_id in sorted(measurement_agent_ids):
            context = point_context.get(agent_id)
            if context is None:
                continue
            x_map, y_map, static_path_loss, _ = context
            observation_id = f"{agent_id}:{tick}"
            sample = oracle.sample_observation(
                observation_id=observation_id,
                elapsed_seconds=elapsed_seconds,
                x_map=x_map,
                y_map=y_map,
                baseline_path_loss_db=static_path_loss,
            )
            observation = CkmObservation(
                observation_id=observation_id,
                elapsed_seconds=elapsed_seconds,
                scene_id="bristol_topology",
                gnb_id=gnb.gnb_id,
                carrier_freq_mhz=gnb.carrier_freq_mhz,
                x_map=x_map,
                y_map=y_map,
                baseline_path_loss_db=static_path_loss,
                observed_path_loss_db=sample.observed_path_loss_db,
                source="controlled_oracle",
                quality=1.0,
            )
            started = time.perf_counter()
            update = tracking_model.observe(observation)
            observation_durations_ms.append((time.perf_counter() - started) * 1000.0)
            if update.accepted:
                accepted_updates += 1
            if tick < train_ticks:
                forecast_model.observe(observation)

    report = {
        "experiment": "physics_informed_online_spatiotemporal_ckm_residual_adaptation",
        "scope": "controlled_simulation_only",
        "scene_id": "bristol_topology",
        "seed": truth_seed,
        "ticks": ticks,
        "tick_ms": tick_ms,
        "forecast_train_ticks": train_ticks,
        "measurement_agent_ids": sorted(measurement_agent_ids),
        "probe_agent_ids": sorted(probe_agent_ids),
        "spatial_holdout_ids": sorted(holdout_points),
        "static_ckm": {
            "cells": len(static_ckm.cells),
            "grid_scale_m": static_ckm.grid_scale_m,
            "indoor_refine_scale_m": static_ckm.indoor_refine_scale_m,
            "version_key": static_ckm.version_key,
        },
        "truth_config": _serialise_truth_config(oracle.config),
        "estimator_config": asdict(estimator_config),
        "summary": {
            "all_tracking_ticks": _summarise(records),
            "spatial_holdout": _summarise(
                [record for record in records if record["scope"] == "spatial_holdout"]
            ),
            "probe_agent": _summarise(
                [record for record in records if record["scope"] == "probe_agent"]
            ),
            "event_active": _summarise(
                [record for record in records if record["event_loss_db"] >= 1.0]
            ),
            "non_event": _summarise(
                [record for record in records if record["event_loss_db"] < 1.0]
            ),
            "frozen_forecast": _summarise(
                [record for record in records if record["tick"] >= train_ticks]
            ),
        },
        "runtime": {
            "accepted_observation_updates": accepted_updates,
            "tracking_observation_count": tracking_model.observation_count,
            "forecast_observation_count": forecast_model.observation_count,
            "feature_count": tracking_model.feature_count,
            "prediction_latency_ms": _latency_summary(prediction_durations_ms),
            "observation_latency_ms": _latency_summary(observation_durations_ms),
            "estimated_state_bytes": _estimated_state_bytes(
                tracking_model.feature_count,
                estimator_config.max_support_observations,
            ),
        },
        "claims": {
            "real_bristol_validation": False,
            "real_measurements": False,
            "scheduler_qos_closed_loop": False,
            "evaluation_order": "predict_score_then_observe",
        },
    }
    return report


def _build_agent_trajectories(
    *,
    scene,
    ticks: int,
    speed_map_units_per_tick: float,
) -> dict[str, list[tuple[float, float]]]:
    definition = load_agent_simulation_definition(DEFAULT_AGENT_CONFIG)
    navigation = NavigationPlanner(
        scene,
        seed=definition.seed,
        cell_size=2.0,
        max_candidates=12,
        max_astar_candidates=6,
    )
    trajectories: dict[str, list[tuple[float, float]]] = {}
    for agent in definition.agents:
        route: list[tuple[float, float]] = [agent.spawn_position]
        current = agent.spawn_position
        for plan_step in definition.plans.get(agent.agent_id, ()):
            if plan_step.stay:
                continue
            result = navigation.plan_path(current, plan_step.destination_ref)
            if result.ok and result.plan is not None:
                segment = list(result.plan.waypoints)
            else:
                destination = navigation.resolve_destination(plan_step.destination_ref)
                segment = [current, destination.position] if destination is not None else [current]
            if segment:
                route.extend(segment[1:] if route[-1] == segment[0] else segment)
                current = route[-1]
        trajectories[agent.agent_id] = [
            _position_on_ping_pong_route(route, tick * speed_map_units_per_tick)
            for tick in range(ticks)
        ]
    return trajectories


def _position_on_ping_pong_route(
    route: list[tuple[float, float]],
    travelled_distance: float,
) -> tuple[float, float]:
    if len(route) <= 1:
        return route[0]
    lengths = [
        math.hypot(end[0] - start[0], end[1] - start[1])
        for start, end in zip(route, route[1:])
    ]
    total = sum(lengths)
    if total <= 1e-9:
        return route[0]
    cycle_position = travelled_distance % (2.0 * total)
    distance = cycle_position if cycle_position <= total else 2.0 * total - cycle_position
    for start, end, segment_length in zip(route, route[1:], lengths):
        if distance <= segment_length:
            ratio = distance / segment_length if segment_length > 0.0 else 0.0
            return (
                start[0] + ratio * (end[0] - start[0]),
                start[1] + ratio * (end[1] - start[1]),
            )
        distance -= segment_length
    return route[-1]


def _summarise(records: list[dict]) -> dict:
    if not records:
        return {"count": 0}
    summary = {"count": len(records)}
    for label, key in (
        ("physical", "physical_error_db"),
        ("static_ckm", "static_error_db"),
        ("online_tracking", "tracking_error_db"),
        ("frozen_forecast", "forecast_error_db"),
    ):
        values = [float(record[key]) for record in records]
        summary[label] = {
            "mae_db": sum(abs(value) for value in values) / len(values),
            "rmse_db": math.sqrt(sum(value * value for value in values) / len(values)),
            "bias_db": sum(values) / len(values),
        }
    accepted = [record for record in records if record["tracking_accepted"]]
    summary["online_tracking"]["accepted_ratio"] = len(accepted) / len(records)
    if accepted:
        summary["online_tracking"]["prediction_interval_90_coverage"] = (
            sum(bool(record["tracking_90_covered"]) for record in accepted) / len(accepted)
        )
        summary["online_tracking"]["mean_support_score"] = sum(
            float(record["tracking_support_score"]) for record in accepted
        ) / len(accepted)
    return summary


def _latency_summary(values_ms: list[float]) -> dict:
    if not values_ms:
        return {"count": 0}
    ordered = sorted(values_ms)
    return {
        "count": len(values_ms),
        "median": statistics.median(ordered),
        "p95": ordered[min(len(ordered) - 1, math.floor(0.95 * (len(ordered) - 1)))],
        "max": ordered[-1],
    }


def _estimated_state_bytes(feature_count: int, max_support_observations: int) -> int:
    # Two coefficient-like vectors, one dense covariance, and bounded
    # (x, y, time) support summaries, assuming doubles.
    return (
        feature_count * feature_count
        + 2 * feature_count
        + 3 * max_support_observations
    ) * 8


def _serialise_truth_config(config: ControlledDynamicChannelConfig) -> dict:
    payload = asdict(config)
    payload["hidden_parameters_exposed_to_estimator"] = False
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Controlled online spatiotemporal CKM ablation (no RAN runtime integration)."
    )
    parser.add_argument("--ticks", type=int, default=120)
    parser.add_argument("--tick-ms", type=float, default=1000.0)
    parser.add_argument("--forecast-train-ticks", type=int)
    parser.add_argument("--grid", type=float, default=100.0)
    parser.add_argument("--indoor-grid", type=float, default=50.0)
    parser.add_argument("--agent-speed", type=float, default=15.0)
    parser.add_argument("--seed", type=int, default=9042)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    report = build_bristol_ablation(
        ticks=args.ticks,
        tick_ms=args.tick_ms,
        forecast_train_ticks=args.forecast_train_ticks,
        grid_scale_m=args.grid,
        indoor_refine_scale_m=args.indoor_grid,
        agent_speed_map_units_per_tick=args.agent_speed,
        truth_seed=args.seed,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2 if args.pretty else None))
    print(f"report: {args.output}")


if __name__ == "__main__":
    main()
