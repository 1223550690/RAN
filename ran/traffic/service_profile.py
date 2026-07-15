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
    """Project implementation detail."""

    return dict(SERVICE_QOS_TABLE.get(service_type, SERVICE_QOS_TABLE["video_upload"]))
