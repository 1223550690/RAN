"""Unit tests for RlcEntity, RlcRetxBlock, and compatibility wrappers."""

from __future__ import annotations

from typing import Any

import pytest

from ran.contracts import Drb, RlcQueue
from ran.protocol.pdcp import PdcpBatch
from ran.protocol.rlc import (
    RlcEntity,
    RlcGrantResult,
    RlcRetxBlock,
    RlcSegment,
    apply_transmission_to_rlc,
    build_rlc_queue,
)
from tests.conftest import make_alloc, make_result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_entity(
    mode: str = "AM",
    **kwargs: Any,
) -> RlcEntity:
    defaults: dict[str, Any] = {
        "ue_id": "u",
        "drb_id": 3,
        "qfi": 9,
        "slice_id": "embb",
        "direction": "UL",
        "mode": mode,
    }

    defaults.update(kwargs)
    return RlcEntity(**defaults)


def _batch(n: int) -> PdcpBatch:
    """Build a dummy PdcpBatch with output_bytes=n."""
    return PdcpBatch(drb_id=3, qfi=9, slice_id="embb",
                     payload_bytes=n, overhead_bytes=0,
                     output_bytes=n, sn_start=0, sn_end=0)


# ---------------------------------------------------------------------------
# RlcEntity.enqueue
# ---------------------------------------------------------------------------

class TestEnqueue:
    def test_enqueue_increments_queued(self):
        rlc = _make_entity()
        rlc.enqueue(_batch(1000))
        assert rlc.queued_bytes == 1000
        rlc.enqueue(_batch(500))
        assert rlc.queued_bytes == 1500

    def test_enqueue_zero(self):
        rlc = _make_entity()
        rlc.enqueue(_batch(0))
        assert rlc.queued_bytes == 0


# ---------------------------------------------------------------------------
# RlcEntity.to_queue_state
# ---------------------------------------------------------------------------

class TestToQueueState:
    def test_returns_rlc_queue(self):
        rlc = _make_entity()
        rlc.enqueue(_batch(1000))
        qs = rlc.to_queue_state()
        assert isinstance(qs, RlcQueue)
        assert qs.queued_bytes == 1000
        assert qs.retransmission_bytes == 0
        assert qs.delivered_bytes == 0
        assert qs.dropped_bytes == 0

    def test_mode_propagated(self):
        for mode in ("TM", "UM", "AM"):
            qs = _make_entity(mode=mode).to_queue_state()
            assert qs.rlc_mode == mode

    def test_retransmission_bytes_from_blocks(self):
        rlc = _make_entity("AM")
        rlc.retx_blocks = [RlcRetxBlock(500, 1), RlcRetxBlock(300, 2)]
        qs = rlc.to_queue_state()
        assert qs.retransmission_bytes == 800


# ---------------------------------------------------------------------------
# RlcEntity.on_grant
# ---------------------------------------------------------------------------

class TestOnGrant:
    def test_drains_new_data(self):
        rlc = _make_entity("UM")
        rlc.enqueue(_batch(5000))
        grant = rlc.on_grant(make_alloc(5000))
        assert grant.actual_sent_bytes == 5000
        assert rlc.queued_bytes == 0
        assert rlc.inflight_new_bytes == 5000

    def test_partial_grant(self):
        rlc = _make_entity("UM")
        rlc.enqueue(_batch(5000))
        grant = rlc.on_grant(make_alloc(3000))
        assert grant.actual_sent_bytes == 3000
        assert rlc.queued_bytes == 2000

    def test_retx_priority_over_new_data(self):
        """Retransmission bytes are drained before new data."""
        rlc = _make_entity("AM")
        rlc.retx_blocks = [RlcRetxBlock(2000, 1)]
        rlc.enqueue(_batch(5000))
        grant = rlc.on_grant(make_alloc(4000))
        assert grant.actual_sent_bytes == 4000
        assert rlc.retransmission_bytes == 0  # retx fully drained
        assert rlc.queued_bytes == 3000  # 5000 - 2000

    def test_retx_partial_drain(self):
        rlc = _make_entity("AM")
        rlc.retx_blocks = [RlcRetxBlock(5000, 1)]
        rlc.enqueue(_batch(1000))
        grant = rlc.on_grant(make_alloc(3000))
        assert grant.actual_sent_bytes == 3000
        assert rlc.retransmission_bytes == 2000
        assert rlc.queued_bytes == 1000

    def test_zero_grant(self):
        rlc = _make_entity("UM")
        rlc.enqueue(_batch(5000))
        grant = rlc.on_grant(make_alloc(0))
        assert grant.actual_sent_bytes == 0
        assert rlc.queued_bytes == 5000

    def test_um_no_retx_blocks(self):
        """UM mode never has retx blocks."""
        rlc = _make_entity("UM")
        rlc.enqueue(_batch(5000))
        rlc.on_grant(make_alloc(5000))
        rlc.on_transmission_result(make_result(1, successful=3000, failed=2000))
        assert rlc.retransmission_bytes == 0
        assert rlc.dropped_bytes == 2000

class TestSegmentationDetails:
    def test_partial_sdu_returns_segment_metadata(self):
        rlc = _make_entity("UM")
        rlc.enqueue(_batch(5000))

        first = rlc.on_grant(make_alloc(3000))

        assert isinstance(first, RlcGrantResult)
        assert first.grant_bytes == 3000
        assert first.actual_sent_bytes == 3000
        assert len(first.segments) == 1

        segment = first.segments[0]
        assert segment.offset_bytes == 0
        assert segment.segment_bytes == 3000
        assert segment.is_first is True
        assert segment.is_last is False

        rlc.on_transmission_result(
            make_result(
                1,
                successful=3000,
                failed=0,
            )
        )

        second = rlc.on_grant(make_alloc(3000))

        assert second.actual_sent_bytes == 2000
        assert second.segments[0].offset_bytes == 3000
        assert second.segments[0].segment_bytes == 2000
        assert second.segments[0].is_first is False
        assert second.segments[0].is_last is True

    def test_one_grant_can_span_multiple_sdus(self):
        rlc = _make_entity("UM")

        rlc.enqueue(_batch(1000))
        rlc.enqueue(_batch(2000))

        grant = rlc.on_grant(make_alloc(1500))

        assert grant.actual_sent_bytes == 1500

        assert [
            segment.segment_bytes
            for segment in grant.segments
        ] == [1000, 500]

        assert grant.segments[0].is_last is True
        assert grant.segments[1].is_first is True
        assert grant.segments[1].is_last is False

        assert rlc.queued_bytes == 1500

    def test_actual_sent_never_exceeds_grant(self):
        rlc = _make_entity("UM")
        rlc.enqueue(_batch(1000))

        grant = rlc.on_grant(make_alloc(5000))

        assert grant.actual_sent_bytes == 1000
        assert grant.actual_sent_bytes <= grant.grant_bytes

        assert sum(
            segment.segment_bytes
            for segment in grant.segments
        ) == grant.actual_sent_bytes

    def test_retransmission_segment_is_returned_first(self):
        rlc = _make_entity("AM")

        rlc.retx_blocks = [
            RlcRetxBlock(
                1000,
                1,
                rlc_sn=7,
                sdu_id=4,
                offset_bytes=200,
            )
        ]

        rlc.enqueue(_batch(1000))

        grant = rlc.on_grant(make_alloc(1500))

        assert [
            segment.is_retransmission
            for segment in grant.segments
        ] == [True, False]

        assert grant.segments[0].rlc_sn == 7
        assert grant.segments[0].offset_bytes == 200
        assert grant.segments[0].segment_bytes == 1000
        assert grant.segments[1].segment_bytes == 500

# ---------------------------------------------------------------------------
# RlcEntity.on_transmission_result — UM mode
# ---------------------------------------------------------------------------

class TestOnTransmissionResultUM:
    def test_successful_bytes_delivered(self):
        rlc = _make_entity("UM")
        rlc.enqueue(_batch(5000))
        rlc.on_grant(make_alloc(5000))
        rlc.on_transmission_result(make_result(1, successful=4000, failed=1000))
        assert rlc.delivered_bytes == 4000

    def test_failed_bytes_dropped(self):
        rlc = _make_entity("UM")
        rlc.enqueue(_batch(5000))
        rlc.on_grant(make_alloc(5000))
        rlc.on_transmission_result(make_result(1, successful=3000, failed=2000))
        assert rlc.dropped_bytes == 2000

    def test_no_retransmission(self):
        rlc = _make_entity("UM")
        rlc.enqueue(_batch(5000))
        rlc.on_grant(make_alloc(5000))
        rlc.on_transmission_result(make_result(1, successful=3000, failed=2000))
        assert rlc.retransmission_bytes == 0


# ---------------------------------------------------------------------------
# RlcEntity.on_transmission_result — AM mode
# ---------------------------------------------------------------------------

class TestOnTransmissionResultAM:
    def test_rlc_retx_bytes_queued(self):
        """rlc_retx_bytes go into RLC retransmission queue."""
        rlc = _make_entity("AM")
        rlc.enqueue(_batch(5000))
        rlc.on_grant(make_alloc(5000))
        rlc.on_transmission_result(make_result(1, successful=3000, failed=2000, rlc_retx=2000))
        assert rlc.retransmission_bytes == 2000
        assert rlc.delivered_bytes == 3000
        assert rlc.dropped_bytes == 0

    def test_harq_retx_bytes_not_in_rlc_queue(self):
        """harq_retx_bytes do NOT enter the RLC retransmission queue."""
        rlc = _make_entity("AM")
        rlc.enqueue(_batch(5000))
        rlc.on_grant(make_alloc(5000))
        rlc.on_transmission_result(make_result(1, successful=3000, failed=2000, rlc_retx=1000, harq_retx=1000))
        assert rlc.retransmission_bytes == 1000  # only rlc_retx
        assert rlc.dropped_bytes == 0  # new data failures not dropped
        # the other 1000 (harq) is handled by HARQ layer, not RLC

    def test_max_retx_attempts_drop(self):
        """Blocks exceeding max_retx_attempts are dropped."""
        rlc = _make_entity("AM", max_retx_attempts=2)
        rlc.enqueue(_batch(5000))
        rlc.on_grant(make_alloc(5000))
        # first failure → attempts=1
        rlc.on_transmission_result(make_result(1, successful=3000, failed=2000, rlc_retx=2000))
        assert rlc.retransmission_bytes == 2000
        assert len(rlc.retx_blocks) == 1
        assert rlc.retx_blocks[0].attempts == 1

        # second failure → attempts=2
        rlc.on_grant(make_alloc(2000))
        rlc.on_transmission_result(make_result(2, successful=0, failed=2000, rlc_retx=2000))
        assert rlc.retransmission_bytes == 2000
        assert rlc.retx_blocks[0].attempts == 2

        # third failure → attempts=3 > max_retx_attempts(2) → dropped
        rlc.on_grant(make_alloc(2000))
        rlc.on_transmission_result(make_result(3, successful=0, failed=2000, rlc_retx=2000))
        assert rlc.retransmission_bytes == 0
        assert rlc.dropped_bytes == 2000

    def test_successful_retx_clears_block(self):
        """Successful retransmission reduces delivered_bytes, clears inflight."""
        rlc = _make_entity("AM")
        rlc.enqueue(_batch(5000))
        rlc.on_grant(make_alloc(5000))
        rlc.on_transmission_result(make_result(1, successful=3000, failed=2000, rlc_retx=2000))
        assert rlc.retransmission_bytes == 2000

        # retx succeeds
        rlc.on_grant(make_alloc(2000))
        rlc.on_transmission_result(make_result(2, successful=2000, failed=0))
        assert rlc.delivered_bytes == 5000
        assert rlc.retransmission_bytes == 0


# ---------------------------------------------------------------------------
# RlcEntity.on_transmission_result — TM mode
# ---------------------------------------------------------------------------

class TestOnTransmissionResultTM:
    def test_tm_drops_all_failures(self):
        rlc = _make_entity("TM")
        rlc.enqueue(_batch(5000))
        rlc.on_grant(make_alloc(5000))
        rlc.on_transmission_result(make_result(1, successful=2000, failed=3000))
        assert rlc.delivered_bytes == 2000
        assert rlc.dropped_bytes == 3000
        assert rlc.retransmission_bytes == 0


# ---------------------------------------------------------------------------
# Byte conservation
# ---------------------------------------------------------------------------

class TestByteConservation:
    def test_um_byte_conservation(self):
        """Total bytes = delivered + dropped + queued + retx + inflight."""
        rlc = _make_entity("UM")
        total_enqueued = 0

        for tick in range(1, 6):
            rlc.enqueue(_batch(2000))
            total_enqueued += 2000
            # grant capped at queue size; result attempted matches actual sent
            grant_result = rlc.on_grant(make_alloc(2000))
            actual_sent = grant_result.actual_sent_bytes

            rlc.on_transmission_result(
                make_result(
                    tick,
                    successful=actual_sent // 2,
                    failed=actual_sent - actual_sent // 2,
                )
            )

        total_accounted = (
            rlc.delivered_bytes + rlc.dropped_bytes
            + rlc.queued_bytes + rlc.retransmission_bytes
            + rlc.inflight_new_bytes + rlc.inflight_retx_bytes
        )
        assert total_accounted == total_enqueued

    def test_am_byte_conservation_simple(self):
        """AM: bytes flow through retx but eventually all accounted for."""
        rlc = _make_entity("AM", max_retx_attempts=10)
        rlc.enqueue(_batch(10000))
        total_enqueued = 10000

        for tick in range(1, 4):
            grant_result = rlc.on_grant(make_alloc(5000))
            actual_sent = grant_result.actual_sent_bytes
            half = actual_sent // 2
            rlc.on_transmission_result(make_result(
                tick, successful=half, failed=actual_sent - half,
                rlc_retx=actual_sent - half
            ))

        total_accounted = (
            rlc.delivered_bytes + rlc.dropped_bytes
            + rlc.queued_bytes + rlc.retransmission_bytes
            + rlc.inflight_new_bytes + rlc.inflight_retx_bytes
        )
        assert total_accounted == total_enqueued


# ---------------------------------------------------------------------------
# Head-of-line delay
# ---------------------------------------------------------------------------

class TestHOLDelay:
    def test_hol_increments_when_queue_nonempty(self):
        rlc = _make_entity("UM")
        rlc.enqueue(_batch(5000))
        rlc.on_grant(make_alloc(3000))
        rlc.on_transmission_result(make_result(1, successful=3000, failed=0, delay=1.5))
        # queue still has 2000, so HOL increases
        assert rlc.head_of_line_delay_ms == 1.5

    def test_hol_does_not_increment_when_queue_empty(self):
        rlc = _make_entity("UM")
        rlc.enqueue(_batch(5000))
        rlc.on_grant(make_alloc(5000))
        rlc.on_transmission_result(make_result(1, successful=5000, failed=0, delay=1.5))
        # queue empty, retx empty → no HOL increment
        assert rlc.head_of_line_delay_ms == 0.0


# ---------------------------------------------------------------------------
# build_rlc_queue (compatibility wrapper)
# ---------------------------------------------------------------------------

class TestBuildRlcQueueCompat:
    def test_returns_rlc_queue(self):
        drb = Drb(3, "u", 10, 9, "embb", "UL", "AM", 1)
        qs = build_rlc_queue(_batch(5000), drb)
        assert isinstance(qs, RlcQueue)
        assert qs.queued_bytes == 5000
        assert qs.retransmission_bytes == 0
        assert qs.rlc_mode == "AM"

    def test_new_fields_default_zero(self):
        drb = Drb(3, "u", 10, 9, "embb", "UL", "UM", 1)
        qs = build_rlc_queue(_batch(5000), drb)
        assert qs.delivered_bytes == 0
        assert qs.dropped_bytes == 0


# ---------------------------------------------------------------------------
# apply_transmission_to_rlc (compatibility wrapper)
# ---------------------------------------------------------------------------

class TestApplyTransmissionToRlcCompat:
    def test_drains_queued(self):
        queue = RlcQueue("u", 3, 9, "embb", "UL", "UM", 5000, 0, 0.0)
        result = make_result(1, successful=3000, failed=2000)
        apply_transmission_to_rlc(queue, result)
        # attempted=5000 drains all 5000 from queued; UM drops failures silently
        assert queue.queued_bytes == 0

    def test_am_requeues_failures(self):
        queue = RlcQueue("u", 3, 9, "embb", "UL", "AM", 5000, 0, 0.0)
        result = make_result(1, successful=3000, failed=2000)
        apply_transmission_to_rlc(queue, result)
        assert queue.retransmission_bytes == 2000

    def test_um_does_not_requeue(self):
        queue = RlcQueue("u", 3, 9, "embb", "UL", "UM", 5000, 0, 0.0)
        result = make_result(1, successful=3000, failed=2000)
        apply_transmission_to_rlc(queue, result)
        assert queue.retransmission_bytes == 0
