from __future__ import annotations

from ran.contracts import IPTrafficBatch, PduSession, UERequest


def build_ip_traffic(request: UERequest, session: PduSession) -> IPTrafficBatch:
    """构造临时字节级流量批次；后续由 IpPacketBatch 实现替换。"""

    endpoint_by_target = {
        "youtube_server": "10.20.1.80",
        "chat_server": "10.20.1.40",
        "voice_server": "10.20.1.60",
    }
    dst_ip = endpoint_by_target.get(request.target, "10.20.1.1")
    return IPTrafficBatch(
        service_id=request.service_instance_id,
        src_ip=session.ue_ip,
        dst_ip=dst_ip,
        protocol="TCP",
        dst_port=443,
        direction=request.direction,
        total_bytes=request.requested_payload_bytes,
        remaining_bytes=request.requested_payload_bytes,
        metadata={
            "intent_id": request.intent_id,
            "service_instance_id": request.service_instance_id,
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
