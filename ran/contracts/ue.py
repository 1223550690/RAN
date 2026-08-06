from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .common import Direction, Position


AccessType = Literal["3gpp", "non_3gpp"]
SelectedAccess = Literal["5g", "wifi", "auto"]


@dataclass(slots=True)
class UEState:
    """Project implementation detail.

    Input fields:
    - ue_id/agent_id: binding relationship between UE and Agent.
    - position: UE's current map coordinates.

    Output fields:
    - rm_state/cm_state/rrc_state: simplified control plane states.
    - ue_ip: UE IP allocated after PDU session establishment.
    - cmax_transmit: Value indicating the configured maximum transmission power of the UE, to be used for the Power Headroom Report.
    """
    

    ue_id: str  # ue_id: UE/handset identifier.
    agent_id: str  # agent_id: identifier of the bound Agent.
    position: Position  # position: UE's current map coordinates.
    cmax_transmit: int = 23  # cmax_transmit: UE maximum transmit power in dBm (tr22068 PHR extension, optional).
    ue_pusch: int = 10  # ue_pusch: nominal PUSCH parameter (tr22068 extension, optional).
    rm_state: str = "DEREGISTERED"  # rm_state: 5GC registration state.
    cm_state: str = "IDLE"  # cm_state: core network connection management state.
    rrc_state: str = "IDLE"  # rrc_state: radio control state between UE and gNB.
    
    ue_ip: str | None = None  # ue_ip: IP obtained by the UE in the PDU session.
    allowed_slices: list[str] = field(default_factory=list)  # allowed_slices: slices the UE is allowed to use.


@dataclass(slots=True)
class UERequest:
    """UE network request generated from a service intent."""

    ue_id: str  # ue_id: identifier of the UE carrying this service.
    agent_id: str  # agent_id: identifier of the Agent the UE belongs to.
    position: Position  # position: UE's current map coordinates.
    direction: Direction  # direction: UL or DL.
    selected_access: SelectedAccess  # selected_access: 5g/wifi/auto.
    access_type: AccessType
    target: str
    dnn: str
    pdu_session_type: str  # pdu_session_type: IPv4/IPv6/IPv4v6.
    service_type: str
    requested_payload_bytes: int  # requested_payload_bytes: amount of data requested at the application layer.
    qos_hint: dict[str, object] = field(default_factory=dict)
    intent_id: str = ""  # intent_id: identifier of the intent this request corresponds to (integration extension, optional).
    service_instance_id: str = ""  # service_instance_id: global identifier of this service instance (integration extension, optional).

    @property
    def size_bytes(self) -> int:
        """Compatibility for the legacy field name size_bytes (historical constructors/reads still use it)."""

        return self.requested_payload_bytes


@dataclass(slots=True)
class AccessSelection:
    """Project implementation detail."""

    selected_access: SelectedAccess
    access_type: AccessType
    access_node_id: str
    reason: str
