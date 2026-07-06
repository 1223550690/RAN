from __future__ import annotations

from ran.contracts import Drb, QoSFlow, UERequest


def map_qos_flow_to_drb(qos_flow: QoSFlow, request: UERequest) -> Drb:
    """SDAP: QFI 到 DRB 的映射。

    输入:
    - qos_flow: QoS Flow/QFI。
    - request: UERequest，用于获取 UE 与方向。

    输出:
    - Drb: RAN 内部数据无线承载。
    """

    # MVP 最小实现：每个 QFI 固定映射到同一个 DRB ID 规则；后续可支持多 QFI 复用 DRB。
    drb_id = 3 if qos_flow.qfi == 9 else qos_flow.qfi
    rlc_mode = "AM" if qos_flow.service_type in {"video_upload", "web"} else "UM"
    return Drb(
        drb_id=drb_id,
        ue_id=request.ue_id,
        pdu_session_id=qos_flow.pdu_session_id,
        qfi=qos_flow.qfi,
        slice_id=qos_flow.slice_id,
        direction=qos_flow.direction,
        rlc_mode=rlc_mode,
        priority=qos_flow.priority,
    )
