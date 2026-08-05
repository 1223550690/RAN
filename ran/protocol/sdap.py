from __future__ import annotations

from ran.contracts import Drb, QoSFlow, UERequest


def map_qos_flow_to_drb(qos_flow: QoSFlow, request: UERequest) -> Drb:
    """Project implementation detail."""

    drb_id = 3 if qos_flow.qfi == 9 else qos_flow.qfi
    # 最小实现：文件上传使用 AM；后续由 bearer policy 显式配置。
    rlc_mode = "AM" if qos_flow.service_type in {"video_upload", "voice_upload", "web"} else "UM"
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
