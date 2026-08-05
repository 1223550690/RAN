from __future__ import annotations

from dataclasses import dataclass, field

from ran.contracts import (
    Direction,
    Drb,
    MacAllocation,
    RlcQueue,
    TransmissionResult,
)

from .pdcp import PdcpBatch

@dataclass(slots=True)
class RlcSdu:
    """Project implementation detail."""

    sdu_id: int
    pdcp_sn_start: int
    pdcp_sn_end: int
    total_bytes: int
    remaining_bytes: int
    next_offset_bytes: int = 0


@dataclass(slots=True)
class RlcSegment:
    """Project implementation detail."""

    rlc_sn: int
    sdu_id: int
    pdcp_sn_start: int
    pdcp_sn_end: int
    offset_bytes: int
    segment_bytes: int
    is_first: bool
    is_last: bool
    is_retransmission: bool = False
    retx_attempt: int = 0


@dataclass(slots=True)
class RlcGrantResult:
    """Project implementation detail."""

    grant_bytes: int
    actual_sent_bytes: int
    segments: list[RlcSegment] = field(default_factory=list)

@dataclass(slots=True)
class RlcRetxBlock:
    """Project implementation detail."""

    bytes_remaining: int
    attempts: int
    rlc_sn: int = -1
    sdu_id: int = -1
    pdcp_sn_start: int = 0
    pdcp_sn_end: int = 0
    offset_bytes: int = 0


@dataclass(slots=True)
class RlcEntity:
    """Project implementation detail."""

    ue_id: str
    drb_id: int
    qfi: int
    slice_id: str
    direction: Direction
    mode: str  # rlc_mode: TM/UM/AM。
    queued_bytes: int = 0
    sdu_queue: list[RlcSdu] = field(default_factory=list)
    retx_blocks: list[RlcRetxBlock] = field(default_factory=list)
    next_sdu_id: int = 0
    next_sn: int = 0
    sn_size_bits: int = 18
    max_retx_attempts: int = 4
    partial_segment_bytes: int = 0
    # inflight tracking — set by on_grant, consumed by on_transmission_result
    inflight_new_bytes: int = 0
    inflight_retx_bytes: int = 0
    inflight_retx_max_attempts: int = 0
    inflight_segments: list[RlcSegment] = field(default_factory=list)
    delivered_bytes: int = 0
    dropped_bytes: int = 0
    head_of_line_delay_ms: float = 0.0

    @property
    def retransmission_bytes(self) -> int:
        """Project implementation detail."""
        return sum(b.bytes_remaining for b in self.retx_blocks)

    def enqueue(self, batch: PdcpBatch) -> None:
        """Project implementation detail."""
        if batch.output_bytes <= 0:
            return

        self.sdu_queue.append(
            RlcSdu(
                sdu_id=self.next_sdu_id,
                pdcp_sn_start=batch.sn_start,
                pdcp_sn_end=batch.sn_end,
                total_bytes=batch.output_bytes,
                remaining_bytes=batch.output_bytes,
            )
        )

        self.next_sdu_id += 1
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

    def _take_next_sn(self) -> int:
        """Project implementation detail."""
        sn = self.next_sn
        self.next_sn = (self.next_sn + 1) % (2 ** self.sn_size_bits)
        return sn

    def on_grant(self, allocation: MacAllocation) -> RlcGrantResult:
        """Project implementation detail.

        Treat ``allocation.scheduled_bytes`` as the MAC grant, build the
        concrete RLC segments that fit in the grant, and return both the
        segment list and the actual bytes handed to PHY.
        """
        grant_bytes = max(0, allocation.scheduled_bytes)
        budget = grant_bytes
        segments: list[RlcSegment] = []

        # 清空上一个 tick 的在途记录
        self.inflight_new_bytes = 0
        self.inflight_retx_bytes = 0
        self.inflight_retx_max_attempts = 0
        self.inflight_segments = []

        # 1. AM 模式下，优先处理重传队列
        retx_sent = 0
        retx_max_attempts = 0
        remaining_blocks: list[RlcRetxBlock] = []

        for block in self.retx_blocks:
            if budget <= 0:
                remaining_blocks.append(block)
                continue

            take = min(block.bytes_remaining, budget)

            rlc_sn = (
                block.rlc_sn
                if block.rlc_sn >= 0
                else self._take_next_sn()
            )

            segments.append(
                RlcSegment(
                    rlc_sn=rlc_sn,
                    sdu_id=block.sdu_id,
                    pdcp_sn_start=block.pdcp_sn_start,
                    pdcp_sn_end=block.pdcp_sn_end,
                    offset_bytes=block.offset_bytes,
                    segment_bytes=take,
                    is_first=False,
                    is_last=take == block.bytes_remaining,
                    is_retransmission=True,
                    retx_attempt=block.attempts,
                )
            )

            retx_sent += take
            retx_max_attempts = max(
                retx_max_attempts,
                block.attempts,
            )

            block.bytes_remaining -= take
            block.offset_bytes += take
            budget -= take

            if block.bytes_remaining > 0:
                block.rlc_sn = rlc_sn
                remaining_blocks.append(block)

        self.retx_blocks = remaining_blocks

        # 2. grant 还有剩余时，处理首传 SDU 队列
        new_sent = 0

        while budget > 0 and self.sdu_queue:
            sdu = self.sdu_queue[0]
            remaining_before = sdu.remaining_bytes
            take = min(remaining_before, budget)

            segment = RlcSegment(
                rlc_sn=self._take_next_sn(),
                sdu_id=sdu.sdu_id,
                pdcp_sn_start=sdu.pdcp_sn_start,
                pdcp_sn_end=sdu.pdcp_sn_end,
                offset_bytes=sdu.next_offset_bytes,
                segment_bytes=take,
                is_first=sdu.next_offset_bytes == 0,
                is_last=take == remaining_before,
            )

            segments.append(segment)

            sdu.remaining_bytes -= take
            sdu.next_offset_bytes += take

            self.queued_bytes -= take
            new_sent += take
            budget -= take

            # 当前 SDU 已经全部切完
            if sdu.remaining_bytes == 0:
                self.sdu_queue.pop(0)

        # 记录跨 tick 的切分位置
        self.partial_segment_bytes = (
            self.sdu_queue[0].next_offset_bytes
            if self.sdu_queue
            else 0
        )

        self.inflight_new_bytes = new_sent
        self.inflight_retx_bytes = retx_sent
        self.inflight_retx_max_attempts = retx_max_attempts
        self.inflight_segments = segments

        actual_sent_bytes = new_sent + retx_sent

        return RlcGrantResult(
            grant_bytes=grant_bytes,
            actual_sent_bytes=actual_sent_bytes,
            segments=segments,
        )

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
            self.inflight_segments = []

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
        queue.retransmission_bytes += result.rlc_retx_bytes
    if queue.queued_bytes > 0 or queue.retransmission_bytes > 0:
        queue.head_of_line_delay_ms += result.transmission_delay_ms
    return queue
