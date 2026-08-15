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
    """An Agent's state and associated objects in the current RAN scenario."""

    agent_id: str  # agent_id: global Agent identifier.
    state: AgentStateSnapshot  # state: most recent AgentStateProvider state.
    intent_ids: list[str] = field(default_factory=list)  # intent_ids: the Agent's set of intents.
    ue_ids: list[str] = field(default_factory=list)  # ue_ids: the set of UEs associated with this Agent.


@dataclass(slots=True)
class IntentContext:
    """Keeps an Intent's lifecycle and the service instances it produced."""

    intent: AgentIntent  # intent: original Agent intent.
    status: IntentStatus = "PENDING"  # status: current Intent lifecycle state.
    service_instance_ids: list[str] = field(default_factory=list)  # service_instance_ids: set of derived service instances.


@dataclass(slots=True)
class UeContext:
    """Keeps UE control plane state and the currently carried service set."""

    state: UEState  # state: UE registration, connection and location state.
    active_service_ids: list[str] = field(default_factory=list)  # active_service_ids: set of unfinished services.


@dataclass(slots=True)
class ServiceCounters:
    """Minimal metrics ledger maintained independently per service instance."""

    attempted_protocol_bytes: int = 0
    delivered_protocol_bytes: int = 0
    permanently_dropped_protocol_bytes: int = 0
    delivered_payload_bytes: int = 0
    permanently_dropped_payload_bytes: int = 0
    n3_loss_bytes: int = 0
    n6_loss_bytes: int = 0


@dataclass(slots=True)
class ServiceContext:
    """Continuous state of one service instance from UERequest through RLC, core network, and metrics."""

    service_instance_id: str  # service_instance_id: global service instance identifier.
    intent_id: str  # intent_id: upstream Intent identifier.
    agent_id: str  # agent_id: Agent owning the service.
    ue_id: str  # ue_id: UE executing the service.
    ue_request: UERequest
    access: AccessSelection
    slice_id: str
    session: PduSession
    traffic: IPTrafficBatch
    qos_flow: QoSFlow
    drb: Drb
    pdcp_batch: PdcpBatch
    rlc_queue: RlcQueue
    content: ServiceContent
    dl_queue: RlcQueue | None = None  # dl_queue: gNB-side queue for downlink services (None for UL services).
    pdcp: object | None = None  # pdcp: xizhe PDCP entity (when running the entity pipeline).
    rlc: object | None = None  # rlc: xizhe RLC entity (when running the entity pipeline).
    intent_type: str = ""  # intent_type: service type (message/video_upload/video_download, etc.; for frontend display).
    upf_buffered_bytes: int = 0  # upf_buffered_bytes: DL buffered bytes on the UPF side (not yet past N3).
    n3_tunnel_id: str | None = None  # n3_tunnel_id: GTP-U tunnel id (dl_{session}/ul_{session}).
    n3_gtp_overhead_bytes: int = 0  # n3_gtp_overhead_bytes: cumulative GTP-U encapsulation overhead (statistics).
    status: ServiceStatus = "INITIALIZING"
    waiting_ticks: int = 0  # waiting_ticks: cumulative ticks spent waiting for allocation (aids congestion/failure detection).
    counters: ServiceCounters = field(default_factory=ServiceCounters)
    last_state: dict[str, object] | None = None


@dataclass(slots=True)
class ServiceContent:
    """Data communicated by the service"""
    recipient: str
    data: str
    sender: str
