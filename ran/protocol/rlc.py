from __future__ import annotations

from ran.contracts import Drb, RlcQueue, TransmissionResult
from .pdcp import PdcpBatch


def build_rlc_queue(batch: PdcpBatch, drb: Drb) -> RlcQueue:
    """Project implementation detail."""

    return RlcQueue(
        ue_id=drb.ue_id,
        drb_id=drb.drb_id,
        qfi=drb.qfi,
        slice_id=drb.slice_id,
        direction=drb.direction,
        rlc_mode=drb.rlc_mode,
        queued_bytes=batch.output_bytes,
        retransmission_bytes=0,
        head_of_line_delay_ms=0.0,
    )


def apply_transmission_to_rlc(queue: RlcQueue, result: TransmissionResult) -> RlcQueue:
    """Project implementation detail."""

    attempted = max(0, result.attempted_bytes)
    sent_from_retx = min(queue.retransmission_bytes, attempted)
    queue.retransmission_bytes = max(0, queue.retransmission_bytes - sent_from_retx)
    sent_from_new_data = max(0, attempted - sent_from_retx)
    queue.queued_bytes = max(0, queue.queued_bytes - sent_from_new_data)
    if queue.rlc_mode == "AM":
        queue.retransmission_bytes += result.failed_bytes
    if queue.queued_bytes > 0 or queue.retransmission_bytes > 0:
        queue.head_of_line_delay_ms += result.transmission_delay_ms
    return queue
