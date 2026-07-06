from __future__ import annotations


def configure_radio_bearer() -> dict[str, str]:
    """预留 gNB-CU-CP 控制面接口。

    输入:
    - MVP 暂无真实 N2/NGAP/RRC 消息。

    输出:
    - 控制面配置说明。
    """

    # MVP 最小实现：只保留接口，后续可接 RRC 和 PDU Session Resource Setup。
    return {"status": "configured", "note": "MVP bearer configuration placeholder"}
