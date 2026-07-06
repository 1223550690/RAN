from __future__ import annotations

from ran.contracts import UEState


def register_ue(ue: UEState) -> UEState:
    """执行最小 UE 注册/连接准备。

    输入:
    - UEState: 原始 UE 状态。

    输出:
    - UEState: 标记为 REGISTERED/CONNECTED。
    """

    # MVP 最小实现：不实现 NAS/RRC/NGAP 消息序列，只更新状态字段。
    ue.rm_state = "REGISTERED"
    ue.cm_state = "CONNECTED"
    ue.rrc_state = "CONNECTED"
    return ue
