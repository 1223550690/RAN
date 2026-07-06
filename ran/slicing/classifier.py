from __future__ import annotations

from ran.traffic.service_profile import service_profile_for


def classify_slice(service_type: str) -> str:
    """业务到切片的最小分类。

    输入:
    - service_type: UERequest 中的业务类型。

    输出:
    - slice_id: embb/urllc/mmtc。
    """

    # MVP 最小实现：直接使用 service profile 中的固定 slice_id。
    return str(service_profile_for(service_type)["slice_id"])
