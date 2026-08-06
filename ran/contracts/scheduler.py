from __future__ import annotations

from dataclasses import dataclass, field

from .bearer import Drb, RlcQueue
from .common import Direction
from .qos import QoSFlow, SlicePolicy
from .radio import ChannelState, MacAllocation


@dataclass(slots=True)
class SchedulerRequest:
    """Complete scheduling snapshot sent by Python to the replaceable Scheduler backend."""

    contract_version: str  # contract_version: cross-language contract version.
    simulation_id: str  # simulation_id: identifier of this simulation run.
    scheduler_request_id: str  # scheduler_request_id: identifier of this decision request.
    tick: int  # tick: current simulation tick.
    gnb_id: str  # gnb_id: identifier of the base station being scheduled.
    direction: Direction  # direction: UL or DL.
    total_prbs: int  # total_prbs: total PRBs available for the current direction.
    rlc_queues: list[RlcQueue]  # rlc_queues: summary of active RLC queues.
    qos_flows: list[QoSFlow]  # qos_flows: list of QoS flow summaries.
    drbs: list[Drb]  # drbs: list of DRB configurations.
    channel_states: list[ChannelState]  # channel_states: list of channel state records.
    slice_policies: list[SlicePolicy]  # slice_policies: list of slice policies.
    harq_feedback: list[dict[str, object]] = field(default_factory=list)
    requirements: list[str] = field(default_factory=list)  # requirements: scheduling requirement tags (tr22068 extension, optional).
    phr: list[float] = field(default_factory=list)  # phr: UE power headroom reports (tr22068 extension, optional).
    slot_ms: float = 1.0  # slot_ms: radio slot duration (ms) represented by this tick; throughput is scaled by the tick's semantic duration.


@dataclass(slots=True)
class SchedulerResult:
    """Decision returned by the Scheduler backend for one SchedulerRequest."""

    contract_version: str  # contract_version: must match the request version.
    simulation_id: str  # simulation_id: must match the request simulation.
    scheduler_request_id: str  # scheduler_request_id: identifier of the corresponding request.
    tick: int  # tick: tick the decision belongs to.
    allocations: list[MacAllocation]  # allocations: list of DRB-to-PRB decisions.
    debug: dict[str, object] = field(default_factory=dict)  # debug: debug information not required for execution.
