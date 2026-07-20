from __future__ import annotations

from dataclasses import dataclass, field

from .bearer import Drb, RlcQueue
from .common import Direction
from .qos import QoSFlow, SlicePolicy
from .radio import ChannelState, MacAllocation


@dataclass(slots=True)
class SchedulerRequest:
    """Scheduler 输入。

    输入字段:
    - rlc_queues/qos_flows/drbs/channel_states/slice_policies。

    输出用途:
    - 可序列化为 JSON 后交给 Java scheduler；当前 MVP 先接 Python fallback。
    """

    tick: int  # tick: 当前仿真 tick。
    direction: Direction  # direction: UL 或 DL。
    total_prbs: int  # total_prbs: 可分配 PRB 总数。
    rlc_queues: list[RlcQueue]  # rlc_queues: RLC 队列摘要。
    qos_flows: list[QoSFlow]  # qos_flows: QoS Flow 列表。
    drbs: list[Drb]  # drbs: DRB 列表。
    channel_states: list[ChannelState]  # channel_states: 信道状态。
    slice_policies: list[SlicePolicy]  # slice_policies: 切片策略。
    phr: float
    harq_feedback: list[dict[str, object]] = field(default_factory=list)  # harq_feedback: HARQ 反馈占位。
    


@dataclass(slots=True)
class SchedulerResult:
    """Scheduler 输出。

    输出字段:
    - allocations: MACAllocation 列表，Python 后续执行 PHY/RLC/QoS 更新。
    """

    tick: int  # tick: 当前仿真 tick。
    allocations: list[MacAllocation]  # allocations: MAC 调度结果。
    debug: dict[str, object] = field(default_factory=dict)  # debug: 调度解释信息。
