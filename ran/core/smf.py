from __future__ import annotations

from ran.contracts import PduSession, UERequest, UEState


def establish_pdu_session(ue: UEState, request: UERequest, *, slice_id: str) -> PduSession:
    """建立最小 PDU Session。

    输入:
    - ue: 已注册 UE。
    - request: UE 业务请求。
    - slice_id: 业务所属切片。

    输出:
    - PduSession: UE IP、DNN、UPF 等用户面上下文。
    """

    # MVP 最小实现：固定分配 IP 和 UPF，不实现完整 SMF/UPF 选择策略。
    ue.ue_ip = ue.ue_ip or "10.20.0.15"
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
