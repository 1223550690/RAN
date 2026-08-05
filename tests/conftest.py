"""Shared fixtures for PDCP/RLC tests."""

from __future__ import annotations

import pytest

from ran.contracts import IPTrafficBatch, MacAllocation, TransmissionResult


# ---------------------------------------------------------------------------
# Traffic fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def small_traffic() -> IPTrafficBatch:
    """10 KB traffic batch — small enough for fast unit tests."""
    return IPTrafficBatch(
        service_id="test_svc",
        src_ip="10.0.0.1",
        dst_ip="10.0.0.2",
        protocol="TCP",
        dst_port=443,
        direction="UL",
        total_bytes=10_000,
        remaining_bytes=10_000,
    )


@pytest.fixture
def empty_traffic() -> IPTrafficBatch:
    """Traffic batch with nothing left to send."""
    return IPTrafficBatch(
        service_id="test_svc",
        src_ip="10.0.0.1",
        dst_ip="10.0.0.2",
        protocol="TCP",
        dst_port=443,
        direction="UL",
        total_bytes=10_000,
        remaining_bytes=0,
    )


# ---------------------------------------------------------------------------
# Allocation / result helpers
# ---------------------------------------------------------------------------

def make_alloc(scheduled_bytes: int, **overrides) -> MacAllocation:
    """Build a MacAllocation with sane defaults."""
    defaults = dict(
        ue_id="u",
        drb_id=3,
        qfi=9,
        slice_id="embb",
        direction="UL",
        prbs=20,
        mcs=10,
        layers=1,
        scheduled_bytes=scheduled_bytes,
        expected_error_rate=0.0,
        is_retransmission=False,
    )
    defaults.update(overrides)
    return MacAllocation(**defaults)


def make_result(
    tick: int,
    *,
    successful: int,
    failed: int,
    rlc_retx: int = 0,
    harq_retx: int = 0,
    dropped: int = 0,
    delay: float = 1.0,
) -> TransmissionResult:
    """Build a TransmissionResult with sane defaults."""
    attempted = successful + failed
    return TransmissionResult(
        tick=tick,
        ue_id="u",
        gnb_id="g",
        drb_id=3,
        qfi=9,
        slice_id="embb",
        direction="UL",
        attempted_bytes=attempted,
        successful_bytes=successful,
        failed_bytes=failed,
        effective_sinr_db=7.8,
        mcs=10,
        prbs=20,
        layers=1,
        harq_ack=failed == 0,
        harq_retx_bytes=harq_retx,
        rlc_retx_bytes=rlc_retx,
        dropped_bytes=dropped,
        transmission_delay_ms=delay,
    )
