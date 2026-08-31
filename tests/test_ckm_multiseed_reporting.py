"""Small deterministic tests for multi-seed CKM report helpers."""

from __future__ import annotations

import math

from experiments.ckm_spatiotemporal_multiseed import SCOPES, aggregate_reports
from experiments.plot_ckm_spatiotemporal_multiseed import _rolling_rmse


def _report(static_rmse: float, online_rmse: float) -> dict:
    model = lambda rmse: {"mae_db": rmse * 0.8, "rmse_db": rmse, "bias_db": 0.1}
    summary = {}
    for scope in SCOPES:
        summary[scope] = {
            "physical": model(static_rmse + 1.0),
            "static_ckm": model(static_rmse),
            "online_tracking": {
                **model(online_rmse),
                "prediction_interval_90_coverage": 0.9,
            },
            "frozen_forecast": model(online_rmse + 0.2),
        }
    return {
        "summary": summary,
        "runtime": {
            "prediction_latency_ms": {"median": 0.2},
            "observation_latency_ms": {"median": 0.3},
        },
    }


def test_aggregate_reports_uses_seed_level_mean_and_std() -> None:
    aggregate = aggregate_reports([_report(4.0, 3.0), _report(6.0, 3.0)])
    tracking = aggregate["scopes"]["all_tracking_ticks"]
    assert tracking["static_ckm"]["rmse_db"]["mean"] == 5.0
    assert tracking["online_tracking"]["rmse_db"]["mean"] == 3.0
    expected = ((25.0) + (50.0)) / 2.0
    assert math.isclose(tracking["relative_rmse_improvement_percent"]["mean"], expected)


def test_rolling_rmse_keeps_temporal_length() -> None:
    result = _rolling_rmse([3.0, 4.0, 0.0], window=2)
    assert len(result) == 3
    assert result[0] == 3.0
    assert math.isclose(result[1], math.sqrt(12.5))
    assert math.isclose(result[2], math.sqrt(8.0))
