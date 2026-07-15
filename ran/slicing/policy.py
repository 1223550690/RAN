from __future__ import annotations

from ran.contracts import SlicePolicy


def default_slice_policies() -> list[SlicePolicy]:
    """Project implementation detail."""

    return [
        SlicePolicy("urllc", priority=1, min_prb_ratio=0.20, max_prb_ratio=0.60, delay_budget_ms=50.0),
        SlicePolicy("embb", priority=3, min_prb_ratio=0.40, max_prb_ratio=0.90, delay_budget_ms=300.0),
        SlicePolicy("mmtc", priority=6, min_prb_ratio=0.05, max_prb_ratio=0.30, delay_budget_ms=500.0),
    ]


def policy_for(slice_id: str) -> SlicePolicy:
    """Project implementation detail."""

    policies = {policy.slice_id: policy for policy in default_slice_policies()}
    return policies.get(slice_id, policies["embb"])
