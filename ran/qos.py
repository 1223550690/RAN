from __future__ import annotations

from ran.contracts import PduSession, QoSFlow, UERequest
from ran.traffic.service_profile import service_profile_for


def build_qos_flow(request: UERequest, session: PduSession) -> QoSFlow:
    """由 UERequest 和 PDU Session 生成 QoS Flow。

    输入:
    - request: UE 业务请求。
    - session: PDU Session。

    输出:
    - QoSFlow。
    """

    profile = service_profile_for(request.service_type)
    # MVP 最小实现：直接使用 service profile；后续可加入 QoS rule、端口、DNN、PCF 策略。
    return QoSFlow(
        pdu_session_id=session.pdu_session_id,
        qfi=int(profile["qfi"]),
        five_qi=int(profile["five_qi"]),
        direction=request.direction,
        service_type=request.service_type,
        priority=int(profile["priority"]),
        packet_delay_budget_ms=float(profile["packet_delay_budget_ms"]),
        packet_error_rate=float(profile["packet_error_rate"]),
        resource_type=str(profile["resource_type"]),
        slice_id=str(profile["slice_id"]),
    )
