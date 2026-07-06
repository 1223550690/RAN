from __future__ import annotations

from ran.contracts import SlicePolicy


def default_slice_policies() -> list[SlicePolicy]:
    """返回默认切片策略。

    输入:
    - 无。

    输出:
    - SlicePolicy 列表，供 scheduler 使用。
    """

    # MVP 最小实现：固定策略；后续 AI/RIC controller 可动态调整这些权重。
    return [
        SlicePolicy("urllc", priority=1, min_prb_ratio=0.20, max_prb_ratio=0.60, delay_budget_ms=50.0),
        SlicePolicy("embb", priority=3, min_prb_ratio=0.40, max_prb_ratio=0.90, delay_budget_ms=300.0),
        SlicePolicy("mmtc", priority=6, min_prb_ratio=0.05, max_prb_ratio=0.30, delay_budget_ms=500.0),
    ]


def policy_for(slice_id: str) -> SlicePolicy:
    """查询单个切片策略。"""

    policies = {policy.slice_id: policy for policy in default_slice_policies()}
    return policies.get(slice_id, policies["embb"])
