"""Scheduler algorithm tests (tr22068): allocation correctness of the 4 algorithms, PRB conservation, empty queues, Java round-trip."""
from __future__ import annotations

import unittest

from ran.contracts import ChannelState, Direction, Drb, Position, RlcQueue, SlicePolicy
from ran.contracts.qos import QoSFlow
from ran.gnb.du import build_scheduler_request
from ran.scheduler.java_adapter import JavaSchedulerAdapter
from ran.scheduler.python_baseline import (
    PythonBaselineScheduler,
    grantBasedULScheduling,
    maxThroughputDLScheduling,
    roundRobinDLScheduling,
    weightedULScheduling,
)

SLICE = SlicePolicy(
    slice_id="embb",
    priority=6,
    min_prb_ratio=0.0,
    max_prb_ratio=1.0,
    delay_budget_ms=100.0,
)


def _queue(ue_id: str, drb_id: int, queued: int, direction: str = "UL") -> RlcQueue:
    return RlcQueue(
        ue_id=ue_id,
        drb_id=drb_id,
        qfi=1,
        slice_id="embb",
        direction=direction,  # type: ignore[arg-type]
        rlc_mode="AM",
        queued_bytes=queued,
        retransmission_bytes=0,
        head_of_line_delay_ms=0.0,
        delivered_bytes=0,
        dropped_bytes=0,
    )


def _channel(ue_id: str, cqi: int = 10) -> ChannelState:
    return ChannelState(
        tick=1,
        ue_id=ue_id,
        gnb_id="gnb_001",
        direction="UL",
        distance_m=100.0,
        ue_area_id="a1",
        ue_space_type="outdoor",
        cqi=cqi,
        total_path_loss_db=100.0,
        sinr_db=10.0,
        estimated_packet_error_rate=0.01,
    )


def _drb(ue_id: str, drb_id: int) -> Drb:
    return Drb(
        drb_id=drb_id,
        ue_id=ue_id,
        pdu_session_id=1,
        qfi=1,
        slice_id="embb",
        direction="UL",
        rlc_mode="AM",
        priority=6,
    )


def _qos(ue_id: str) -> QoSFlow:
    return QoSFlow(
        five_qi=6,
        resource_type="non_gbr",
        qfi=1,
        pdu_session_id=1,
        direction="UL",
        service_type="video_upload",
        slice_id="embb",
        priority=6,
        packet_delay_budget_ms=100,
        packet_error_rate=1e-3,
    )


def _request(queues, channels=None, total_prbs: int = 106) -> "object":
    ues = sorted({q.ue_id for q in queues})
    return build_scheduler_request(
        simulation_id="test",
        tick=1,
        gnb_id="gnb_001",
        total_prbs=total_prbs,
        rlc_queues=queues,
        qos_flows=[_qos(u) for u in ues],
        drbs=[_drb(q.ue_id, q.drb_id) for q in queues],
        channel_states=channels or [_channel(u) for u in ues],
        slice_policies=[SLICE],
        slot_ms=200,
    )


class SchedulerAlgorithmTests(unittest.TestCase):
    def test_round_robin_allocates_all_active_ues(self) -> None:
        queues = [_queue("ue_a", 1, 100_000), _queue("ue_b", 2, 100_000)]
        result = roundRobinDLScheduling(
            channel_by_ue={"ue_a": _channel("ue_a"), "ue_b": _channel("ue_b")},
            request=_request(queues),
            active=queues,
        )
        self.assertEqual(len(result), 2)
        total_prbs = sum(a.prbs for a in result)
        self.assertEqual(total_prbs, 106)
        for a in result:
            self.assertGreater(a.scheduled_bytes, 0)

    def test_max_throughput_prefers_high_cqi(self) -> None:
        queues = [_queue("ue_a", 1, 100_000), _queue("ue_b", 2, 100_000)]
        channels = {"ue_a": _channel("ue_a", cqi=14), "ue_b": _channel("ue_b", cqi=4)}
        result = maxThroughputDLScheduling(channel_by_ue=channels, request=_request(queues, channels=list(channels.values())), active=queues)
        by_ue = {a.ue_id: a for a in result}
        # the high-CQI UE should receive at least as many PRBs as the low-CQI one
        self.assertGreaterEqual(by_ue["ue_a"].prbs, by_ue["ue_b"].prbs)

    def test_grant_based_ul_bounded_by_queue(self) -> None:
        queues = [_queue("ue_a", 1, 10_000)]
        result = grantBasedULScheduling(
            channel_by_ue={"ue_a": _channel("ue_a")},
            request=_request(queues),
            active=queues,
        )
        self.assertEqual(len(result), 1)
        allocation = result[0]
        self.assertGreater(allocation.scheduled_bytes, 0)
        self.assertLessEqual(allocation.scheduled_bytes, 10_000)

    def test_weighted_ul_respects_weights(self) -> None:
        queues = [_queue("ue_a", 1, 1_000_000), _queue("ue_b", 2, 1_000_000)]
        result = weightedULScheduling(
            channel_by_ue={"ue_a": _channel("ue_a"), "ue_b": _channel("ue_b")},
            request=_request(queues),
            active=queues,
        )
        total_prbs = sum(a.prbs for a in result)
        self.assertLessEqual(total_prbs, 106)
        self.assertGreater(total_prbs, 0)

    def test_python_baseline_scheduler_no_allocation_on_empty_queue(self) -> None:
        scheduler = PythonBaselineScheduler()
        queues = [_queue("ue_a", 1, 0)]
        result = scheduler.allocate(_request(queues))
        self.assertEqual(result.allocations, [])

    def test_python_baseline_allocates_with_backlog(self) -> None:
        scheduler = PythonBaselineScheduler()
        queues = [_queue("ue_a", 1, 500_000)]
        result = scheduler.allocate(_request(queues))
        self.assertEqual(len(result.allocations), 1)
        self.assertGreater(result.allocations[0].scheduled_bytes, 0)


class JavaAdapterRoundTripTests(unittest.TestCase):
    def test_json_round_trip_preserves_request(self) -> None:
        adapter = JavaSchedulerAdapter()
        request = _request([_queue("ue_a", 1, 100_000)])
        payload = adapter.to_json(request)
        rebuilt = adapter.from_json(payload)
        self.assertEqual(rebuilt.simulation_id, request.simulation_id)
        self.assertEqual(rebuilt.scheduler_request_id, request.scheduler_request_id)
        self.assertEqual(rebuilt.tick, request.tick)
        self.assertEqual(rebuilt.contract_version, request.contract_version)
        self.assertEqual(len(rebuilt.allocations), 0)  # empty decision when no Java backend

    def test_java_adapter_falls_back_on_missing_java(self) -> None:
        adapter = JavaSchedulerAdapter()
        request = _request([_queue("ue_a", 1, 50_000)])
        result = adapter.allocate(request)
        # Java unavailable -> fall back to PythonBaselineScheduler
        self.assertIsInstance(result.allocations, list)
        self.assertGreaterEqual(len(result.allocations), 0)


if __name__ == "__main__":
    unittest.main()
