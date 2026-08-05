from __future__ import annotations

from ran.contracts import PduSession, UERequest, UEState


def establish_pdu_session(
    ue: UEState,
    request: UERequest,
    *,
    slice_id: str,
    ue_ip: str | None = None,
) -> PduSession:
    """建立最小 PDU Session；ue_ip 参数用于多 UE mock 的地址隔离。"""

    ue.ue_ip = ue.ue_ip or ue_ip or "10.20.0.15"
    return PduSession(
        pdu_session_id=10,
        ue_id=ue.ue_id,
        dnn=request.dnn,
        slice_id=slice_id,
        pdu_session_type=request.pdu_session_type,
        ue_ip=ue.ue_ip,
        smf_id="smf_001",
        upf_id="internet_upf",
    )
