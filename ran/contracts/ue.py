from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .common import Direction, Position


AccessType = Literal["3gpp", "non_3gpp"]
SelectedAccess = Literal["5g", "wifi", "auto"]


@dataclass(slots=True)
class UEState:
    """Project implementation detail."""

    ue_id: str
    agent_id: str
    position: Position
    rm_state: str = "DEREGISTERED"
    cm_state: str = "IDLE"
    rrc_state: str = "IDLE"
    ue_ip: str | None = None
    allowed_slices: list[str] = field(default_factory=list)


@dataclass(slots=True)
class UERequest:
    """Project implementation detail."""

    ue_id: str
    agent_id: str
    position: Position
    direction: Direction
    selected_access: SelectedAccess  # selected_access: 5g/wifi/auto。
    access_type: AccessType
    target: str
    dnn: str
    pdu_session_type: str  # pdu_session_type: IPv4/IPv6/IPv4v6。
    service_type: str
    size_bytes: int
    qos_hint: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class AccessSelection:
    """Project implementation detail."""

    selected_access: SelectedAccess
    access_type: AccessType
    access_node_id: str
    reason: str
