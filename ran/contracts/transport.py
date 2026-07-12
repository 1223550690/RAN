from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class N3ForwardingResult:
    """Project implementation detail."""

    tunnel_id: str
    teid: int  # teid: GTP-U TEID。
    ue_id: str
    pdu_session_id: int  # pdu_session_id: PDU Session。
    upf_id: str
    forwarded_bytes: int
    n3_delay_ms: float
    n3_loss_bytes: int


@dataclass(slots=True)
class N6DeliveryResult:
    """Project implementation detail."""

    dnn: str  # dnn: Data Network Name。
    target: str
    delivered_bytes: int
    n6_delay_ms: float
    n6_loss_bytes: int
