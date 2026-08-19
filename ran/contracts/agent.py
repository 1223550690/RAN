from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .common import Position


AgentStatus = Literal["READY", "ACTIVE", "PAUSED", "COMPLETED", "FAILED"]


@dataclass(slots=True)
class AgentIntent:
    """A single service intent submitted by an Agent to the network scenario."""

    intent_id: str  # intent_id: globally unique intent identifier.
    agent_id: str  # agent_id: identifier of the Agent that created this intent.
    agent_pos: Position  # agent_pos: Agent map coordinates when the intent was created.
    action: str  # action: everyday action such as upload/send_message.
    target: str  # target: name of the target data network service.
    content_type: str  # content_type: content type such as video/text/audio.
    service_type: str  # service_type: stable service type used for QoS and slice classification.
    requested_payload_bytes: int  # requested_payload_bytes: amount of data requested for transfer at the application layer.
    created_tick: int = 0  # created_tick: simulation tick when the intent was created.
    duration_seconds: float | None = None  # duration_seconds: duration of continuous services (e.g. video_call); None for data-volume-terminated services.
    qos_hint: dict | None = None  # qos_hint: QoS parameter hint; defaults are used by build_ue_request when absent.
    direction: str = "UL"  # direction: traffic direction UL/DL (integration extension, defaults to uplink, backward compatible).
    recipient: str | None = None
    content: str | None = None
    sender: str | None = None

    


@dataclass(slots=True)
class AgentStateSnapshot:
    """Read-only state snapshot returned by AgentStateProvider at a given tick."""

    agent_id: str  # agent_id: Agent identifier frozen when the scenario was set up.
    tick: int  # tick: simulation tick this state belongs to.
    position: Position  # position: Agent's current map coordinates.
    status: AgentStatus  # status: Agent's current running status.
    # The following fields are Agent subsystem extensions, with defaults for backward compatibility.
    role: str = ""  # role: role, e.g. student/teacher/staff.
    activity_state: str = ""  # activity_state: activity state, e.g. planning/walking/network_active.
    current_intent_id: str | None = None  # current_intent_id: identifier of the currently active intent.
    destination_id: str | None = None  # destination_id: semantic reference of the current destination.
    current_room_id: str | None = None  # current_room_id: identifier of the current area.
    waypoint_index: int = 0  # waypoint_index: index of the current waypoint.
    waypoint_count: int = 0  # waypoint_count: total number of waypoints.
    waypoints: list[Position] = field(default_factory=list)  # waypoints: currently planned waypoints (for map rendering, optional).
    last_transition_tick: int = 0  # last_transition_tick: tick of the most recent state transition.
    error: str | None = None  # error: most recent error message, None when no error.
