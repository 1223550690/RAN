from __future__ import annotations

from dataclasses import dataclass, field

from .bearer import Drb, RlcQueue
from .common import Direction
from .qos import QoSFlow, SlicePolicy
from .radio import ChannelState, MacAllocation


@dataclass(slots=True)
class SchedulerRequest:
    """Python 发给可替换 Scheduler 后端的完整调度快照。"""

    contract_version: str  # contract_version: 跨语言合同版本。
    simulation_id: str  # simulation_id: 本次仿真标识。
    scheduler_request_id: str  # scheduler_request_id: 本次决策请求标识。
    tick: int  # tick: 当前仿真 tick。
    gnb_id: str  # gnb_id: 被调度的基站标识。
    direction: Direction  # direction: UL 或 DL。
    total_prbs: int  # total_prbs: 当前方向可用 PRB 总量。
    rlc_queues: list[RlcQueue]  # rlc_queues: 活跃 RLC 队列摘要。
    qos_flows: list[QoSFlow]  # qos_flows: QoS Flow 摘要列表。
    drbs: list[Drb]  # drbs: DRB 配置列表。
    channel_states: list[ChannelState]  # channel_states: 信道状态 record 列表。
    slice_policies: list[SlicePolicy]  # slice_policies: 切片策略列表。
    harq_feedback: list[dict[str, object]] = field(default_factory=list)


@dataclass(slots=True)
class SchedulerResult:
    """Scheduler 后端针对一个 SchedulerRequest 返回的决策。"""

    contract_version: str  # contract_version: 必须与请求版本一致。
    simulation_id: str  # simulation_id: 必须与请求仿真一致。
    scheduler_request_id: str  # scheduler_request_id: 对应的请求标识。
    tick: int  # tick: 决策所属 tick。
    allocations: list[MacAllocation]  # allocations: DRB 到 PRB 的决策列表。
    debug: dict[str, object] = field(default_factory=dict)  # debug: 非执行必需的调试信息。
