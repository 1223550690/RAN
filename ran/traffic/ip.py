from __future__ import annotations

from ran.contracts import IPTrafficBatch, PduSession, UERequest


def build_ip_traffic(request: UERequest, session: PduSession) -> IPTrafficBatch:
    """生成 IP 业务批次。

    输入:
    - request: UE 业务请求。
    - session: PDU Session。

    输出:
    - IPTrafficBatch: MVP 按字节批次推进，不逐包拆分。
    """

    # MVP 最小实现：youtube_server 固定映射到一个模拟 IP，不做 DNS/路由。
    dst_ip = "10.20.1.80" if request.target == "youtube_server" else "10.20.1.1"
    return IPTrafficBatch(
        service_id=f"{request.ue_id}_{request.service_type}_001",
        src_ip=session.ue_ip,
        dst_ip=dst_ip,
        protocol="TCP",
        dst_port=443,
        direction=request.direction,
        total_bytes=request.size_bytes,
        remaining_bytes=request.size_bytes,
        metadata={
            "ue_id": request.ue_id,
            "direction": request.direction,
            "dnn": request.dnn,
            "service_type": request.service_type,
            "pdu_session_id": session.pdu_session_id,
            "slice_id": session.slice_id,
            "selected_access": request.selected_access,
            "access_type": request.access_type,
        },
    )
