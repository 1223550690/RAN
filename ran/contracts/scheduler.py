from __future__ import annotations

from dataclasses import dataclass, field

from .bearer import Drb, RlcQueue
from .common import Direction
from .qos import QoSFlow, SlicePolicy
from .radio import ChannelState, MacAllocation


@dataclass(slots=True)
class SchedulerRequest:
    """Project implementation detail."""

    tick: int
    direction: Direction
    total_prbs: int
    rlc_queues: list[RlcQueue]
    qos_flows: list[QoSFlow]
    drbs: list[Drb]
    channel_states: list[ChannelState]
    slice_policies: list[SlicePolicy]
    harq_feedback: list[dict[str, object]] = field(default_factory=list)


@dataclass(slots=True)
class SchedulerResult:
    """Project implementation detail."""

    tick: int
    allocations: list[MacAllocation]
    debug: dict[str, object] = field(default_factory=dict)
