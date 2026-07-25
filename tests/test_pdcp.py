"""Unit tests for PdcpEntity and PdcpBatch."""

from __future__ import annotations

import math

import pytest

from ran.protocol.pdcp import PdcpBatch, PdcpEntity, build_pdcp_batch


# ---------------------------------------------------------------------------
# PdcpEntity.process
# ---------------------------------------------------------------------------

class TestPdcpEntityProcess:
    """process() produces correct PdcpBatch and advances state."""

    def test_basic_single_tick(self, small_traffic):
        """All traffic consumed in one tick; SN starts at 0."""
        entity = PdcpEntity(drb_id=3, qfi=9, slice_id="embb")
        batch = entity.process(small_traffic, tick=1)

        assert batch.drb_id == 3
        assert batch.qfi == 9
        assert batch.slice_id == "embb"
        assert batch.payload_bytes == 10_000
        assert batch.sn_start == 0
        # 10000 / 1500 = 6.67 → 7 PDUs
        expected_pdus = math.ceil(10_000 / 1500)
        assert batch.sn_end == expected_pdus - 1
        assert batch.overhead_bytes == expected_pdus * 2
        assert batch.output_bytes == batch.payload_bytes + batch.overhead_bytes
        assert small_traffic.remaining_bytes == 0
        assert entity.next_sn == expected_pdus

    def test_two_tick_partial(self):
        """per_tick_inflow_bytes splits traffic across ticks."""
        from ran.contracts import IPTrafficBatch

        traffic = IPTrafficBatch("s", "a", "b", "TCP", 443, "UL", 10_000, 10_000)
        entity = PdcpEntity(drb_id=3, qfi=9, slice_id="embb", per_tick_inflow_bytes=4_000)

        b1 = entity.process(traffic, tick=1)
        assert b1.payload_bytes == 4_000
        assert b1.sn_start == 0
        assert b1.sn_end == math.ceil(4_000 / 1500) - 1
        assert traffic.remaining_bytes == 6_000

        b2 = entity.process(traffic, tick=2)
        # per_tick_inflow caps at 4000 even though 6000 remains
        assert b2.payload_bytes == 4_000
        assert b2.sn_start == b1.sn_end + 1
        assert traffic.remaining_bytes == 2_000

        b3 = entity.process(traffic, tick=3)
        assert b3.payload_bytes == 2_000
        assert traffic.remaining_bytes == 0

        b4 = entity.process(traffic, tick=4)
        assert b4.payload_bytes == 0
        assert b4.output_bytes == 0

    def test_empty_traffic_returns_empty_batch(self, empty_traffic):
        """No remaining bytes → empty batch with output_bytes=0."""
        entity = PdcpEntity(drb_id=3, qfi=9, slice_id="embb")
        batch = entity.process(empty_traffic, tick=1)

        assert batch.payload_bytes == 0
        assert batch.overhead_bytes == 0
        assert batch.output_bytes == 0
        assert entity.next_sn == 0  # SN not advanced

    def test_sn_rollover(self):
        """SN wraps around when reaching 2**sn_size_bits."""
        from ran.contracts import IPTrafficBatch

        entity = PdcpEntity(
            drb_id=3, qfi=9, slice_id="embb",
            sn_size_bits=3,  # modulus = 8
            nominal_packet_size=1500,
        )
        # 1500 bytes → 1 PDU per tick → SN advances by 1 each tick
        for tick in range(1, 10):
            traffic = IPTrafficBatch("s", "a", "b", "TCP", 443, "UL", 1500, 1500)
            batch = entity.process(traffic, tick=tick)
            assert batch.sn_start == (tick - 1) % 8
            assert batch.sn_end == (tick - 1) % 8

    def test_header_overhead_is_applied(self):
        """Overhead = pdu_count * header_overhead_bytes."""
        from ran.contracts import IPTrafficBatch

        traffic = IPTrafficBatch("s", "a", "b", "TCP", 443, "UL", 3000, 3000)
        entity = PdcpEntity(drb_id=3, qfi=9, slice_id="embb", header_overhead_bytes=4)
        batch = entity.process(traffic, tick=1)

        pdu_count = math.ceil(3000 / 1500)  # = 2
        assert batch.overhead_bytes == pdu_count * 4
        assert batch.output_bytes == 3000 + pdu_count * 4

    def test_reserved_hooks_are_noop(self):
        """Reserved hooks return their input unchanged."""
        entity = PdcpEntity(drb_id=3, qfi=9, slice_id="embb")

        assert entity._apply_ciphering(100) == 100
        assert entity._apply_integrity(200) == 200
        assert entity._compress_header(300) == 300
        batch = PdcpBatch(3, 9, "embb", 100, 2, 102, 0, 0)
        assert entity.reorder(batch) is batch
        assert entity.deduplicate(batch) is batch

    def test_output_bytes_equals_payload_plus_overhead(self, small_traffic):
        """Invariant: output_bytes == payload_bytes + overhead_bytes."""
        entity = PdcpEntity(drb_id=3, qfi=9, slice_id="embb")
        batch = entity.process(small_traffic, tick=1)
        assert batch.output_bytes == batch.payload_bytes + batch.overhead_bytes


# ---------------------------------------------------------------------------
# build_pdcp_batch (compatibility wrapper)
# ---------------------------------------------------------------------------

class TestBuildPdcpBatchCompat:
    """build_pdcp_batch preserves original signature and behavior."""

    def test_returns_pdcp_batch(self, small_traffic):
        from ran.contracts import Drb

        drb = Drb(3, "u", 10, 9, "embb", "UL", "AM", 1)
        batch = build_pdcp_batch(small_traffic, drb)
        assert isinstance(batch, PdcpBatch)

    def test_sn_start_is_zero(self, small_traffic):
        from ran.contracts import Drb

        drb = Drb(3, "u", 10, 9, "embb", "UL", "AM", 1)
        batch = build_pdcp_batch(small_traffic, drb)
        assert batch.sn_start == 0

    def test_consumes_traffic(self, small_traffic):
        from ran.contracts import Drb

        drb = Drb(3, "u", 10, 9, "embb", "UL", "AM", 1)
        build_pdcp_batch(small_traffic, drb)
        assert small_traffic.remaining_bytes == 0
