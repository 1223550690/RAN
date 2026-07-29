from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address

from .common import Direction


@dataclass(slots=True)
class PduSession:
    """A simplified 5GS PDU session.

    The identity is scoped to a UE.  The MVP models the 3GPP-defined identity
    range (1-15) and currently supports IPv4 user-plane addressing.
    """

    pdu_session_id: int
    ue_id: str
    dnn: str
    slice_id: str
    pdu_session_type: str  # pdu_session_type: IPv4/IPv6/IPv4v6。
    ue_ip: str
    smf_id: str
    upf_id: str
    state: str = "ACTIVE"

    def __post_init__(self) -> None:
        if not 1 <= self.pdu_session_id <= 15:
            raise ValueError("pdu_session_id must be in the range 1..15")
        if not self.ue_id:
            raise ValueError("ue_id must not be empty")
        if not self.dnn:
            raise ValueError("dnn must not be empty")
        if not self.slice_id:
            raise ValueError("slice_id must not be empty")
        if self.pdu_session_type not in {"IPv4", "IPv6", "IPv4v6"}:
            raise ValueError(f"unsupported PDU session type: {self.pdu_session_type}")
        if self.state not in {"ACTIVE", "INACTIVE", "RELEASED"}:
            raise ValueError(f"unsupported PDU session state: {self.state}")
        address_version = ip_address(self.ue_ip).version
        if self.pdu_session_type == "IPv4" and address_version != 4:
            raise ValueError("IPv4 PDU sessions require an IPv4 UE address")
        if self.pdu_session_type == "IPv6" and address_version != 6:
            raise ValueError("IPv6 PDU sessions require an IPv6 UE address")


@dataclass(slots=True)
class QoSFlow:
    """A QoS flow carried by a PDU session.

    QFI and 5QI are deliberately validated separately: QFI is a six-bit flow
    identifier (1-63), while 5QI selects a standardized QoS characteristic and
    can therefore contain values such as 80.
    """

    pdu_session_id: int
    qfi: int  # qfi: QoS Flow Identifier。
    five_qi: int
    direction: Direction
    service_type: str
    priority: int
    packet_delay_budget_ms: float
    packet_error_rate: float
    resource_type: str
    slice_id: str
    gbr_mbps: float | None = None
    mbr_mbps: float | None = None

    def __post_init__(self) -> None:
        if not 1 <= self.qfi <= 63:
            raise ValueError("qfi must be in the range 1..63")
        if not 1 <= self.five_qi <= 255:
            raise ValueError("five_qi must be in the range 1..255")
        if not 1 <= self.priority <= 127:
            raise ValueError("priority must be in the range 1..127")
        if self.packet_delay_budget_ms <= 0:
            raise ValueError("packet_delay_budget_ms must be positive")
        if not 0 <= self.packet_error_rate <= 1:
            raise ValueError("packet_error_rate must be in the range 0..1")
        if self.resource_type not in {"non_gbr", "gbr", "delay_critical_gbr"}:
            raise ValueError(f"unsupported resource_type: {self.resource_type}")
        if self.gbr_mbps is not None and self.gbr_mbps <= 0:
            raise ValueError("gbr_mbps must be positive when provided")
        if self.mbr_mbps is not None and self.mbr_mbps <= 0:
            raise ValueError("mbr_mbps must be positive when provided")
        if self.gbr_mbps is not None and self.mbr_mbps is not None and self.gbr_mbps > self.mbr_mbps:
            raise ValueError("gbr_mbps must not exceed mbr_mbps")
        if self.resource_type != "non_gbr" and self.gbr_mbps is None:
            raise ValueError("GBR QoS flows require gbr_mbps")


@dataclass(slots=True)
class SlicePolicy:
    """Project implementation detail."""

    slice_id: str
    priority: int
    min_prb_ratio: float
    max_prb_ratio: float
    delay_budget_ms: float
