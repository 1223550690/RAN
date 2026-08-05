"""Agent 状态机。

状态:READY → PLANNING → WALKING → NETWORK_PENDING → NETWORK_ACTIVE → PLANNING …
终态:DONE(无更多计划)/ FAILED(计划或导航失败)。

约束(由转移表强制):
- WALKING 时不得产生网络流量:只有到达(NETWORK_PENDING)后才能提交意图。
- NETWORK_ACTIVE 时坐标冻结:该状态不进入任何移动转移。
- 每个 Agent 同时只有一个活跃网络意图:NETWORK_* 状态互斥。
"""

from __future__ import annotations

from typing import Literal

AgentState = Literal[
    "READY",
    "PLANNING",
    "WALKING",
    "NETWORK_PENDING",
    "NETWORK_ACTIVE",
    "DONE",
    "FAILED",
]

AgentEvent = Literal[
    "start_planning",
    "plan_ready",
    "plan_failed",
    "no_more_plans",
    "arrived",
    "intent_submitted",
    "intent_completed",
    "intent_failed",
    "terminate",
]

# 状态 -> 可接受事件。
_TRANSITIONS: dict[AgentState, set[AgentEvent]] = {
    "READY": {"start_planning", "terminate"},
    "PLANNING": {"plan_ready", "plan_failed", "no_more_plans", "terminate"},
    "WALKING": {"arrived", "terminate"},
    "NETWORK_PENDING": {"intent_submitted", "terminate"},
    "NETWORK_ACTIVE": {"intent_completed", "intent_failed", "terminate"},
    "FAILED": {"start_planning", "terminate"},
    "DONE": set(),
}

_EVENT_TARGET: dict[tuple[AgentState, AgentEvent], AgentState] = {
    ("READY", "start_planning"): "PLANNING",
    ("PLANNING", "plan_ready"): "WALKING",
    ("PLANNING", "plan_failed"): "FAILED",
    ("PLANNING", "no_more_plans"): "DONE",
    ("WALKING", "arrived"): "NETWORK_PENDING",
    ("NETWORK_PENDING", "intent_submitted"): "NETWORK_ACTIVE",
    ("NETWORK_ACTIVE", "intent_completed"): "PLANNING",
    ("NETWORK_ACTIVE", "intent_failed"): "PLANNING",
    ("FAILED", "start_planning"): "PLANNING",
    ("DONE", "terminate"): "DONE",
    ("READY", "terminate"): "DONE",
    ("PLANNING", "terminate"): "DONE",
    ("WALKING", "terminate"): "DONE",
    ("NETWORK_PENDING", "terminate"): "DONE",
    ("NETWORK_ACTIVE", "terminate"): "DONE",
}

_LIFECYCLE_BY_STATE: dict[AgentState, str] = {
    "READY": "READY",
    "PLANNING": "ACTIVE",
    "WALKING": "ACTIVE",
    "NETWORK_PENDING": "ACTIVE",
    "NETWORK_ACTIVE": "ACTIVE",
    "DONE": "COMPLETED",
    "FAILED": "FAILED",
}


class AgentStateMachine:
    def __init__(self, initial: AgentState = "READY") -> None:
        self.state: AgentState = initial
        self.last_transition_tick: int = 0

    def can(self, event: AgentEvent) -> bool:
        return event in _TRANSITIONS.get(self.state, set())

    def transition(self, event: AgentEvent, tick: int) -> AgentState:
        target = _EVENT_TARGET.get((self.state, event))
        if target is None:
            raise ValueError(f"invalid transition: {self.state} + {event}")
        self.state = target
        self.last_transition_tick = tick
        return self.state

    @property
    def lifecycle_status(self) -> str:
        """映射到 ran.AgentStatus 兼容的生命周期状态。"""

        return _LIFECYCLE_BY_STATE[self.state]

    @property
    def activity_state(self) -> str:
        """对外暴露的活动状态名。"""

        return self.state.lower()
