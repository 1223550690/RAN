from __future__ import annotations

from ran.contracts import SlicePolicy
from .policy import default_slice_policies


def update_slice_policies() -> list[SlicePolicy]:
    """预留 AI/RIC-like 切片控制器接口。

    输入:
    - MVP 暂无动态网络状态输入。

    输出:
    - SlicePolicy 列表。
    """

    # MVP 最小实现：返回固定策略；后续可接入神经网络或 RIC-like 控制回路。
    return default_slice_policies()
