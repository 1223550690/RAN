from __future__ import annotations


SERVICE_QOS_TABLE: dict[str, dict[str, object]] = {
    "video_upload": {
        "qfi": 9,
        "five_qi": 9,
        "priority": 5,
        "packet_delay_budget_ms": 300.0,
        "packet_error_rate": 1e-6,
        "resource_type": "non_gbr",
        "slice_id": "embb",
    },
    "game": {
        "qfi": 80,
        "five_qi": 80,
        "priority": 2,
        "packet_delay_budget_ms": 50.0,
        "packet_error_rate": 1e-3,
        "resource_type": "non_gbr",
        "slice_id": "urllc",
    },
    "message": {
        "qfi": 9,
        "five_qi": 9,
        "priority": 7,
        "packet_delay_budget_ms": 500.0,
        "packet_error_rate": 1e-6,
        "resource_type": "non_gbr",
        "slice_id": "mmtc",
    },
}


def service_profile_for(service_type: str) -> dict[str, object]:
    """查询业务 QoS 模板。

    输入:
    - service_type: video_upload/game/message 等业务类型。

    输出:
    - QoS profile 字典，供 QoSFlow 和切片分类使用。
    """

    # MVP 最小实现：使用固定表；后续可替换为配置文件或 5QI 标准表。
    return dict(SERVICE_QOS_TABLE.get(service_type, SERVICE_QOS_TABLE["video_upload"]))
