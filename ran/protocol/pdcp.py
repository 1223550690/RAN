from __future__ import annotations

from dataclasses import dataclass

from ran.contracts import Drb, IPTrafficBatch


@dataclass(slots=True)
class PdcpBatch:
    """Project implementation detail."""

    drb_id: int
    qfi: int
    slice_id: str
    payload_bytes: int
    overhead_bytes: int
    output_bytes: int
    sn_start: int
    sn_end: int


def build_pdcp_batch(traffic: IPTrafficBatch, drb: Drb, *, max_batch_bytes: int | None = None) -> PdcpBatch:
    """Project implementation detail."""

    payload = min(traffic.remaining_bytes, max_batch_bytes or traffic.remaining_bytes)
    pdu_count = max(1, (payload + 1499) // 1500)
    overhead = pdu_count * 2
    return PdcpBatch(
        drb_id=drb.drb_id,
        qfi=drb.qfi,
        slice_id=drb.slice_id,
        payload_bytes=payload,
        overhead_bytes=overhead,
        output_bytes=payload + overhead,
        sn_start=0,
        sn_end=pdu_count - 1,
    )
