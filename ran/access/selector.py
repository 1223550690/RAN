from __future__ import annotations

from ran.contracts import AccessSelection, GnbSite, UERequest


def select_access(request: UERequest, gnb: GnbSite) -> AccessSelection:
    """选择 UE 业务接入方式。

    输入:
    - request: UERequest，含 selected_access/access_type。
    - gnb: 当前单小区 gNB。

    输出:
    - AccessSelection: 当前服务节点和接入类型。
    """

    if request.selected_access == "wifi":
        # MVP 最小实现：只记录 non-3GPP 意图，仍不进入独立 Wi-Fi 链路。
        return AccessSelection("wifi", "non_3gpp", "wifi_reserved", "Wi-Fi 接入仅预留字段，MVP 不执行")
    return AccessSelection("5g", "3gpp", gnb.gnb_id, "MVP 默认使用单小区 5G gNB")
