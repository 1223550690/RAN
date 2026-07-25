from __future__ import annotations

from dataclasses import dataclass, field

from ran.contracts import Drb, MacAllocation, RlcQueue, TransmissionResult
from .pdcp import PdcpBatch


@dataclass(slots=True)
class RlcRetxBlock:
    """Project implementation detail."""

    bytes_remaining: int
    attempts: int


@dataclass(slots=True)
class RlcEntity:
    """Project implementation detail."""

    ue_id: str
    drb_id: int
    qfi: int
    slice_id: str
    direction: str
    mode: str  # rlc_mode: TM/UM/AM。
    queued_bytes: int = 0
    retx_blocks: list[RlcRetxBlock] = field(default_factory=list)
    next_sn: int = 0
    sn_size_bits: int = 18
    max_retx_attempts: int = 4
    partial_segment_bytes: int = 0
    # inflight tracking — set by on_grant, consumed by on_transmission_result
    inflight_new_bytes: int = 0
    inflight_retx_bytes: int = 0
    inflight_retx_max_attempts: int = 0
    delivered_bytes: int = 0
    dropped_bytes: int = 0
    head_of_line_delay_ms: float = 0.0

    @property
    def retransmission_bytes(self) -> int:
        """Project implementation detail."""
        return sum(b.bytes_remaining for b in self.retx_blocks)

    def enqueue(self, batch: PdcpBatch) -> None:
        """Project implementation detail."""
        self.queued_bytes += batch.output_bytes

    def to_queue_state(self) -> RlcQueue:
        """Project implementation detail."""
        return RlcQueue(
            ue_id=self.ue_id,
            drb_id=self.drb_id,
            qfi=self.qfi,
            slice_id=self.slice_id,
            direction=self.direction,
            rlc_mode=self.mode,
            queued_bytes=self.queued_bytes,
            retransmission_bytes=self.retransmission_bytes,
            head_of_line_delay_ms=self.head_of_line_delay_ms,
            delivered_bytes=self.delivered_bytes,
            dropped_bytes=self.dropped_bytes,
        )

    def on_grant(self, allocation: MacAllocation) -> int:
        """Project implementation detail.

        Dequeue bytes within ``allocation.scheduled_bytes`` — retransmission
        queue first (AM only), then new data queue.  Returns total bytes
        handed to PHY.  Tracks inflight state for ``on_transmission_result``.
        """
        budget = max(0, allocation.scheduled_bytes)
        sent = 0

        # 1) retransmission queue — AM only; UM/TM retx_blocks is always empty
        retx_sent = 0
        retx_max_attempts = 0
        remaining_blocks: list[RlcRetxBlock] = []
        for block in self.retx_blocks:
            if budget <= 0:
                remaining_blocks.append(block)
                continue
            take = min(block.bytes_remaining, budget)
            retx_sent += take
            retx_max_attempts = max(retx_max_attempts, block.attempts)
            block.bytes_remaining -= take
            if block.bytes_remaining > 0:
                remaining_blocks.append(block)
            budget -= take
            sent += take
        self.retx_blocks = remaining_blocks
        self.inflight_retx_bytes = retx_sent
        self.inflight_retx_max_attempts = retx_max_attempts

        # 2) new data queue
        take = min(self.queued_bytes, budget)
        self.queued_bytes -= take
        sent += take
        self.inflight_new_bytes = take

        return sent

    def on_transmission_result(self, result: TransmissionResult) -> None:
        """Project implementation detail.

        Consume PHY feedback and update delivered / retransmission / dropped
        counters according to the RLC mode.

        Key semantic: ``result.rlc_retx_bytes`` is the portion that must enter
        RLC retransmission; ``result.harq_retx_bytes`` is handled at the HARQ
        layer and does **not** enter the RLC retransmission queue.
        """
        # all successful bytes (both from new data and retx) count as delivered
        self.delivered_bytes += result.successful_bytes

        if self.mode == "AM":
            # rlc_retx_bytes → RLC retransmission queue (increment attempts)
            retx_bytes = max(0, result.rlc_retx_bytes)
            if retx_bytes > 0:
                next_attempts = self.inflight_retx_max_attempts + 1
                if next_attempts > self.max_retx_attempts:
                    self.dropped_bytes += retx_bytes
                else:
                    self.retx_blocks.append(
                        RlcRetxBlock(bytes_remaining=retx_bytes, attempts=next_attempts)
                    )
            # harq_retx_bytes → HARQ fast retransmission (not in RLC queue)
            # new data failures → first retransmission attempt
            new_failed = max(0, result.failed_bytes - result.rlc_retx_bytes - result.harq_retx_bytes)
            if new_failed > 0:
                self.retx_blocks.append(
                    RlcRetxBlock(bytes_remaining=new_failed, attempts=1)
                )
            # reset inflight
            self.inflight_retx_bytes = 0
            self.inflight_retx_max_attempts = 0
            self.inflight_new_bytes = 0
        else:
            # UM / TM — no retransmission; all failed bytes are dropped
            self.dropped_bytes += result.failed_bytes
            self.inflight_retx_bytes = 0
            self.inflight_retx_max_attempts = 0
            self.inflight_new_bytes = 0

        # head-of-line delay
        if self.queued_bytes > 0 or self.retransmission_bytes > 0:
            self.head_of_line_delay_ms += result.transmission_delay_ms


def build_rlc_queue(batch: PdcpBatch, drb: Drb) -> RlcQueue:
    """Project implementation detail.

    Compatibility wrapper — preserves the original call signature and return
    type for callers that have not yet migrated to ``RlcEntity``.
    """
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
    """Project implementation detail.

    Compatibility wrapper — preserves the original in-place mutation semantics
    for callers that have not yet migrated to ``RlcEntity``.
    """
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
