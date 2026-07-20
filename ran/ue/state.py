from __future__ import annotations

from ran.contracts import Position, UEState


def build_demo_ue_state(*, agent_id: str, ue_id: str, position: Position) -> UEState:
    """创建测试场景 UE 状态。

    输入:
    - agent_id/ue_id/position: 学生活动中心房间内的 Agent/手机位置。

    输出:
    - UEState: 后续由 AMF/SMF 更新注册、连接和 IP 状态。
    """

    return UEState(
        ue_id=ue_id,
        agent_id=agent_id,
        position=position,
        allowed_slices=["embb", "urllc", "mmtc"],
        cmax_transmit = 23,
        ue_pusch = 0,
    )
