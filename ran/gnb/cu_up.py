from __future__ import annotations

from ran.contracts import N3ForwardingResult, PduSession, TransmissionResult


def forward_to_n3(result: TransmissionResult, session: PduSession) -> N3ForwardingResult:
    """gNB-CU-UP 通过 N3/GTP-U 转发用户面数据。

    输入:
    - result: RU/DU 成功接收后的传输结果。
    - session: PDU Session。

    输出:
    - N3ForwardingResult。
    """

    # MVP 最小实现：不实现真实 PDCP/SDAP 接收和 GTP-U header，只记录 TEID 与字节数。
    return N3ForwardingResult(
        tunnel_id=f"n3_tunnel_{session.pdu_session_id}",
        teid=1000 + session.pdu_session_id,
        ue_id=session.ue_id,
        pdu_session_id=session.pdu_session_id,
        upf_id=session.upf_id,
        forwarded_bytes=result.successful_bytes,
        n3_delay_ms=2.0,
        n3_loss_bytes=0,
    )
