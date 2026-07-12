from __future__ import annotations

from ran.contracts import EndToEndResult, QosMetrics


def build_end_to_end_result(
    *,
    service_id: str,
    ue_id: str,
    target: str,
    slice_id: str,
    access_type: str,
    requested_bytes: int,
    delivered_bytes: int,
    qos: QosMetrics,
) -> EndToEndResult:
    """Project implementation detail."""

    return EndToEndResult(
        service_id=service_id,
        ue_id=ue_id,
        target=target,
        slice_id=slice_id,
        access_type=access_type,
        requested_bytes=requested_bytes,
        delivered_bytes=delivered_bytes,
        failed_bytes=max(0, requested_bytes - delivered_bytes),
        qos=qos,
    )
