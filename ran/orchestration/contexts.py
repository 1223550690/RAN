from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ran.contracts import (
    AccessSelection,
    AgentIntent,
    AgentStateSnapshot,
    Drb,
    IPTrafficBatch,
    PduSession,
    QoSFlow,
    RlcQueue,
    UERequest,
    UEState,
)
from ran.protocol.pdcp import PdcpBatch


IntentStatus = Literal["PENDING", "ACTIVE", "COMPLETED", "FAILED"]
ServiceStatus = Literal["INITIALIZING", "ACTIVE", "WAITING_FOR_ALLOCATION", "COMPLETED", "FAILED"]


@dataclass(slots=True)
class AgentContext:
    """一个 Agent 在当前 RAN 场景中的状态与关联对象。"""

    agent_id: str  # agent_id: Agent 全局标识。
    state: AgentStateSnapshot  # state: 最近一次 AgentStateProvider 状态。
    intent_ids: list[str] = field(default_factory=list)  # intent_ids: 该 Agent 的意图集合。
    ue_ids: list[str] = field(default_factory=list)  # ue_ids: 该 Agent 关联的 UE 集合。


@dataclass(slots=True)
class IntentContext:
    """保存一个 Intent 的生命周期及其产生的业务实例。"""

    intent: AgentIntent  # intent: 原始 Agent 意图。
    status: IntentStatus = "PENDING"  # status: 当前 Intent 生命周期状态。
    service_instance_ids: list[str] = field(default_factory=list)  # service_instance_ids: 派生业务集合。


@dataclass(slots=True)
class UeContext:
    """保存 UE 控制面状态和当前承载的业务集合。"""

    state: UEState  # state: UE 注册、连接和位置状态。
    active_service_ids: list[str] = field(default_factory=list)  # active_service_ids: 未结束业务集合。


@dataclass(slots=True)
class ServiceCounters:
    """按业务实例独立维护的最小指标账本。"""

    attempted_protocol_bytes: int = 0
    delivered_protocol_bytes: int = 0
    permanently_dropped_protocol_bytes: int = 0
    delivered_payload_bytes: int = 0
    permanently_dropped_payload_bytes: int = 0
    n3_loss_bytes: int = 0
    n6_loss_bytes: int = 0


@dataclass(slots=True)
class ServiceContext:
    """一个业务实例从 UERequest 到 RLC、核心网和 metrics 的连续状态。"""

    service_instance_id: str  # service_instance_id: 全局业务实例标识。
    intent_id: str  # intent_id: 上游 Intent 标识。
    agent_id: str  # agent_id: 业务所属 Agent。
    ue_id: str  # ue_id: 执行业务的 UE。
    ue_request: UERequest
    access: AccessSelection
    slice_id: str
    session: PduSession
    traffic: IPTrafficBatch
    qos_flow: QoSFlow
    drb: Drb
    pdcp_batch: PdcpBatch
    rlc_queue: RlcQueue
    status: ServiceStatus = "INITIALIZING"
    counters: ServiceCounters = field(default_factory=ServiceCounters)
    last_state: dict[str, object] | None = None
