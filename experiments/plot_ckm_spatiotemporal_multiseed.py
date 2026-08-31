"""Create report-ready line figures from the multi-seed CKM experiment."""

from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import json
import math
from pathlib import Path
import statistics

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_ROOT / "outputs" / "ckm_spatiotemporal_multiseed.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "report" / "ckm_spatiotemporal"

STATIC_COLOR = "#5B6573"
ONLINE_COLOR = "#0072B2"
TRUTH_COLOR = "#D55E00"
SUPPORT_COLOR = "#009E73"
UNCERTAINTY_COLOR = "#56B4E9"
EVENT_COLOR = "#E69F00"


def _setup_style() -> None:
    plt.rcParams.update(
        {
            "font.size": 10,
            "axes.titlesize": 11,
            "axes.labelsize": 10,
            "legend.fontsize": 9,
            "figure.dpi": 140,
            "savefig.dpi": 300,
            "axes.grid": True,
            "grid.alpha": 0.25,
            "grid.linewidth": 0.7,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )


def _mean_std(series: list[list[float]]) -> tuple[list[float], list[float]]:
    if not series:
        return [], []
    length = min(len(values) for values in series)
    means = [statistics.fmean(values[index] for values in series) for index in range(length)]
    stds = [
        statistics.stdev(values[index] for values in series) if len(series) > 1 else 0.0
        for index in range(length)
    ]
    return means, stds


def _rolling_rmse(values: list[float], window: int) -> list[float]:
    result = []
    for index in range(len(values)):
        sample = values[max(0, index - window + 1) : index + 1]
        result.append(math.sqrt(sum(value * value for value in sample) / len(sample)))
    return result


def _records_by_tick(report: dict, *, scope: str | None = None) -> dict[int, list[dict]]:
    grouped: dict[int, list[dict]] = defaultdict(list)
    for record in report["records"]:
        if scope is None or record["scope"] == scope:
            grouped[int(record["tick"])].append(record)
    return dict(sorted(grouped.items()))


def _event_bounds(report: dict) -> tuple[float, float, float, float]:
    event = report["truth_config"]["event"]
    start = float(event["start_seconds"])
    ramp_end = start + float(event["ramp_seconds"])
    active_end = ramp_end + float(event["active_seconds"])
    recovery_end = active_end + float(event["recovery_seconds"])
    return start, ramp_end, active_end, recovery_end


def _shade_event(ax, report: dict, *, show_bounds: bool = True) -> None:
    start, _, _, recovery_end = _event_bounds(report)
    if show_bounds:
        ax.axvline(start, color=STATIC_COLOR, alpha=0.55, lw=0.8, ls=":")
        ax.axvline(recovery_end, color=STATIC_COLOR, alpha=0.55, lw=0.8, ls=":")


def plot_tracking_over_time(payload: dict, output_dir: Path, *, window: int = 10) -> None:
    static_seed_series = []
    online_seed_series = []
    elapsed = []
    for report in payload["reports"]:
        grouped = _records_by_tick(report)
        ticks = sorted(grouped)
        elapsed = [float(grouped[tick][0]["elapsed_seconds"]) for tick in ticks]
        static_tick_errors = [
            math.sqrt(statistics.fmean(float(row["static_error_db"]) ** 2 for row in grouped[tick]))
            for tick in ticks
        ]
        online_tick_errors = [
            math.sqrt(statistics.fmean(float(row["tracking_error_db"]) ** 2 for row in grouped[tick]))
            for tick in ticks
        ]
        static_seed_series.append(_rolling_rmse(static_tick_errors, window))
        online_seed_series.append(_rolling_rmse(online_tick_errors, window))

    static_mean, _ = _mean_std(static_seed_series)
    online_mean, _ = _mean_std(online_seed_series)
    fig, ax = plt.subplots(figsize=(7.2, 4.1), constrained_layout=True)
    ax.plot(
        elapsed,
        static_mean,
        color=STATIC_COLOR,
        lw=1.8,
        ls="--",
        marker="o",
        markevery=10,
        markersize=3.5,
        label="Static CKM",
    )
    ax.plot(
        elapsed,
        online_mean,
        color=ONLINE_COLOR,
        lw=1.8,
        marker="s",
        markevery=10,
        markersize=3.5,
        label="Online spatiotemporal CKM",
    )
    _shade_event(ax, payload["reports"][0])
    ax.set_xlabel("Elapsed time (s)")
    ax.set_ylabel(f"{window}-tick rolling RMSE (dB)")
    ax.legend(frameon=False, ncol=2, loc="upper left")
    _save(fig, output_dir, "fig_ckm_tracking_over_time")


def plot_event_adaptation(payload: dict, output_dir: Path) -> None:
    truth_series = []
    online_series = []
    support_series = []
    elapsed = []
    for report in payload["reports"]:
        rows = sorted(
            (
                row
                for row in report["records"]
                if row["point_id"] == "holdout_event_center"
            ),
            key=lambda row: row["tick"],
        )
        elapsed = [float(row["elapsed_seconds"]) for row in rows]
        truth_series.append([-float(row["static_error_db"]) for row in rows])
        online_series.append(
            [
                float(row["tracking_error_db"]) - float(row["static_error_db"])
                for row in rows
            ]
        )
        support_series.append([float(row["tracking_support_score"]) for row in rows])

    truth_mean, _ = _mean_std(truth_series)
    online_mean, _ = _mean_std(online_series)
    support_mean, _ = _mean_std(support_series)
    fig, (ax_top, ax_bottom) = plt.subplots(
        2,
        1,
        figsize=(7.2, 5.1),
        sharex=True,
        gridspec_kw={"height_ratios": (2.6, 0.75)},
        constrained_layout=True,
    )
    ax_top.plot(
        elapsed,
        truth_mean,
        color=TRUTH_COLOR,
        lw=2.0,
        label="Hidden truth residual",
        zorder=2,
    )
    ax_top.plot(
        elapsed,
        online_mean,
        color=ONLINE_COLOR,
        lw=1.8,
        marker="s",
        markevery=10,
        markersize=3.5,
        label="Estimated online correction",
    )
    ax_top.axhline(0.0, color=STATIC_COLOR, lw=1.2, ls="--", label="Static CKM correction")
    _shade_event(ax_top, payload["reports"][0])
    ax_top.set_ylabel("Residual relative to static CKM (dB)")
    ax_top.legend(frameon=False, ncol=3, loc="upper left")

    ax_bottom.plot(
        elapsed,
        support_mean,
        color=SUPPORT_COLOR,
        lw=1.6,
        marker="o",
        markevery=10,
        markersize=3.0,
    )
    _shade_event(ax_bottom, payload["reports"][0], show_bounds=False)
    ax_bottom.set_xlabel("Elapsed time (s)")
    ax_bottom.set_ylabel("Support score")
    ax_bottom.set_ylim(-0.03, 1.03)
    _save(fig, output_dir, "fig_ckm_event_adaptation")


def plot_forecast_horizon(payload: dict, output_dir: Path) -> None:
    static_seed_series = []
    forecast_seed_series = []
    horizons = []
    for report in payload["reports"]:
        train_ticks = int(report["forecast_train_ticks"])
        tick_seconds = float(report["tick_ms"]) / 1000.0
        grouped = _records_by_tick(report)
        ticks = [tick for tick in sorted(grouped) if tick >= train_ticks]
        horizons = [(tick - train_ticks + 1) * tick_seconds for tick in ticks]
        static_seed_series.append(
            [
                math.sqrt(statistics.fmean(float(row["static_error_db"]) ** 2 for row in grouped[tick]))
                for tick in ticks
            ]
        )
        forecast_seed_series.append(
            [
                math.sqrt(statistics.fmean(float(row["forecast_error_db"]) ** 2 for row in grouped[tick]))
                for tick in ticks
            ]
        )

    static_mean, _ = _mean_std(static_seed_series)
    forecast_mean, _ = _mean_std(forecast_seed_series)
    fig, ax = plt.subplots(figsize=(7.2, 4.1), constrained_layout=True)
    ax.plot(
        horizons,
        static_mean,
        color=STATIC_COLOR,
        lw=1.8,
        ls="--",
        marker="o",
        markevery=5,
        markersize=3.5,
        label="Static CKM",
    )
    ax.plot(
        horizons,
        forecast_mean,
        color=ONLINE_COLOR,
        lw=1.8,
        marker="s",
        markevery=5,
        markersize=3.5,
        label="Frozen online model",
    )
    ax.set_xlabel("Forecast horizon (s)")
    ax.set_ylabel("Per-tick RMSE (dB)")
    ax.legend(frameon=False, ncol=2, loc="upper left")
    _save(fig, output_dir, "fig_ckm_forecast_horizon")


def plot_uncertainty_over_time(payload: dict, output_dir: Path) -> None:
    abs_error_series = []
    interval_series = []
    elapsed = []
    for report in payload["reports"]:
        grouped = _records_by_tick(report)
        ticks = sorted(grouped)
        elapsed = [float(grouped[tick][0]["elapsed_seconds"]) for tick in ticks]
        abs_error_series.append(
            [statistics.fmean(abs(float(row["tracking_error_db"])) for row in grouped[tick]) for tick in ticks]
        )
        interval_series.append(
            [
                1.6448536269514722
                * statistics.fmean(float(row["tracking_std_db"]) for row in grouped[tick])
                for tick in ticks
            ]
        )

    error_mean, error_std = _mean_std(abs_error_series)
    interval_mean, interval_std = _mean_std(interval_series)
    fig, ax = plt.subplots(figsize=(7.2, 4.1), constrained_layout=True)
    _line_with_band(ax, elapsed, error_mean, error_std, "Mean absolute prediction error", ONLINE_COLOR)
    _line_with_band(ax, elapsed, interval_mean, interval_std, "Nominal 90% half-width", UNCERTAINTY_COLOR)
    _shade_event(ax, payload["reports"][0])
    ax.set_title(f"Prediction error and uncertainty over time ({len(payload['seeds'])} seeds)")
    ax.set_xlabel("Elapsed time (s)")
    ax.set_ylabel("Magnitude (dB)")
    ax.legend(frameon=False, ncol=2, loc="upper left")
    _save(fig, output_dir, "fig_ckm_uncertainty_over_time")


def plot_scope_summary(payload: dict, output_dir: Path) -> None:
    scope_specs = (
        ("all_tracking_ticks", "All points", "online_tracking"),
        ("spatial_holdout", "Spatial hold-out", "online_tracking"),
        ("event_active", "Dynamic event", "online_tracking"),
        ("non_event", "Non-event", "online_tracking"),
        ("probe_agent", "Probe Agent", "online_tracking"),
        ("frozen_forecast", "Frozen forecast", "frozen_forecast"),
    )
    aggregate = payload["aggregate"]["scopes"]
    x = list(range(len(scope_specs)))
    static_mean = [aggregate[key]["static_ckm"]["rmse_db"]["mean"] for key, _, _ in scope_specs]
    static_std = [aggregate[key]["static_ckm"]["rmse_db"]["std"] for key, _, _ in scope_specs]
    online_mean = [aggregate[key][model]["rmse_db"]["mean"] for key, _, model in scope_specs]
    online_std = [aggregate[key][model]["rmse_db"]["std"] for key, _, model in scope_specs]

    fig, ax = plt.subplots(figsize=(7.6, 4.3), constrained_layout=True)
    ax.errorbar(
        [value - 0.08 for value in x],
        static_mean,
        yerr=static_std,
        color=STATIC_COLOR,
        marker="o",
        lw=1.8,
        capsize=3,
        label="Static CKM",
    )
    ax.errorbar(
        [value + 0.08 for value in x],
        online_mean,
        yerr=online_std,
        color=ONLINE_COLOR,
        marker="s",
        lw=1.8,
        capsize=3,
        label="Online / frozen model",
    )
    ax.set_xticks(x, [label for _, label, _ in scope_specs], rotation=18, ha="right")
    ax.set_title(f"RMSE comparison across evaluation scopes ({len(payload['seeds'])} seeds)")
    ax.set_ylabel("Seed-level RMSE, mean ± SD (dB)")
    ax.legend(frameon=False, ncol=2, loc="upper right")
    _save(fig, output_dir, "fig_ckm_scope_rmse_summary")


def write_summary_csv(payload: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "table_ckm_multiseed_summary.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            (
                "scope",
                "static_rmse_mean_db",
                "static_rmse_std_db",
                "selected_rmse_mean_db",
                "selected_rmse_std_db",
                "relative_improvement_mean_percent",
                "relative_improvement_std_percent",
            )
        )
        for scope, values in payload["aggregate"]["scopes"].items():
            selected = "frozen_forecast" if scope == "frozen_forecast" else "online_tracking"
            improvement = values["relative_rmse_improvement_percent"]
            writer.writerow(
                (
                    scope,
                    values["static_ckm"]["rmse_db"]["mean"],
                    values["static_ckm"]["rmse_db"]["std"],
                    values[selected]["rmse_db"]["mean"],
                    values[selected]["rmse_db"]["std"],
                    improvement["mean"],
                    improvement["std"],
                )
            )


def _line_with_band(
    ax,
    x,
    mean,
    std,
    label: str,
    color: str,
    *,
    linestyle: str = "-",
    band_alpha: float = 0.10,
) -> None:
    lower = [value - spread for value, spread in zip(mean, std)]
    upper = [value + spread for value, spread in zip(mean, std)]
    ax.plot(x, mean, color=color, lw=2.0, ls=linestyle, label=label, zorder=2)
    ax.fill_between(x, lower, upper, color=color, alpha=band_alpha, linewidth=0, zorder=1)


def _save(fig, output_dir: Path, stem: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for suffix in ("png", "pdf"):
        fig.savefig(output_dir / f"{stem}.{suffix}", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot multi-seed CKM line figures.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--rolling-window", type=int, default=10)
    args = parser.parse_args()
    if args.rolling_window <= 0:
        raise ValueError("rolling-window must be positive")

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    if not payload.get("reports"):
        raise ValueError("multi-seed input contains no reports")
    if any("records" not in report for report in payload["reports"]):
        raise ValueError("multi-seed reports must include per-tick records")

    _setup_style()
    plot_tracking_over_time(payload, args.output_dir, window=args.rolling_window)
    plot_event_adaptation(payload, args.output_dir)
    plot_forecast_horizon(payload, args.output_dir)
    plot_uncertainty_over_time(payload, args.output_dir)
    plot_scope_summary(payload, args.output_dir)
    write_summary_csv(payload, args.output_dir)
    print(f"figures: {args.output_dir}")


if __name__ == "__main__":
    main()
