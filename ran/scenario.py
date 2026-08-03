from __future__ import annotations

from dataclasses import asdict

from ran.access import select_access
from ran.contracts import AgentIntent, Position
from ran.core import deliver_to_data_network, establish_pdu_session, forward_via_upf, register_ue
from ran.gnb import build_scheduler_request, forward_to_n3, receive_radio
from ran.metrics import build_end_to_end_result, calculate_qos, summarize_slice_usage
from ran.protocol import apply_transmission_to_rlc, build_pdcp_batch, build_rlc_queue, process_sdap
from ran.qos import build_qos_flow
from ran.radio import estimate_channel, load_gnb_site_from_scene, transmit
from ran.scheduler import JavaSchedulerAdapter
from ran.slicing import classify_slice
from ran.slicing.controller import update_slice_policies
from ran.traffic import build_ip_traffic
from ran.transport import apply_backhaul, build_n3_result, forward_n6
from ran.ue import build_demo_ue_state, build_ue_request


class RanUploadScenario:
    """Project implementation detail."""

    def __init__(self, scene, scheduler=None) -> None:
        self.scene = scene
        self.scheduler = scheduler or JavaSchedulerAdapter()
        self.intent = AgentIntent(
            agent_id="student_a",
            agent_pos=Position(520.0, 430.0),
            action="upload",
            target="youtube_server",
            content_type="video",
            size_bytes=100 * 1024 * 1024,
        )
        self.gnb = load_gnb_site_from_scene(scene)
        self.ue_state = build_demo_ue_state(
            agent_id=self.intent.agent_id,
            ue_id="student_a_phone",
            position=self.intent.agent_pos,
        )
        self.ue_state = register_ue(self.ue_state)
        self.ue_request = build_ue_request(self.intent, ue_id=self.ue_state.ue_id, selected_access="5g")
        self.access = select_access(self.ue_request, self.gnb)
        self.slice_id = classify_slice(self.ue_request.service_type)
        self.session = establish_pdu_session(self.ue_state, self.ue_request, slice_id=self.slice_id)
        self.traffic = build_ip_traffic(self.ue_request, self.session)
        self.qos_flow = build_qos_flow(self.ue_request, self.session, traffic=self.traffic)
        self.sdap_output = process_sdap(self.traffic, self.qos_flow, self.ue_request)
        self.drb = self.sdap_output.drb
        self.pdcp_batch = build_pdcp_batch(self.sdap_output)
        self.rlc_queue = build_rlc_queue(self.pdcp_batch, self.drb)
        self.slice_policies = update_slice_policies()
        self.completed = False
        self.ticks_executed = 0
        self.cumulative_attempted_bytes = 0
        self.cumulative_successful_bytes = 0
        self.cumulative_failed_bytes = 0
        self.cumulative_dropped_bytes = 0
        self.cumulative_n3_loss_bytes = 0
        self.cumulative_n6_loss_bytes = 0
        self.last_state: dict[str, object] | None = None

    def step(self, tick: int) -> dict[str, object]:
        """Project implementation detail."""

        if self.completed:
            return self.snapshot(tick=tick, status="completed")

        channel = estimate_channel(tick=tick, scene=self.scene, ue_request=self.ue_request, gnb=self.gnb)
        scheduler_request = build_scheduler_request(
            tick=tick,
            total_prbs=self.gnb.total_prbs,
            rlc_queues=[self.rlc_queue],
            qos_flows=[self.qos_flow],
            drbs=[self.drb],
            channel_states=[channel],
            slice_policies=self.slice_policies,
        )
        scheduler_result = self.scheduler.allocate(scheduler_request)
        if not scheduler_result.allocations:
            self.completed = True
            return self.snapshot(tick=tick, status="no_allocation")

        allocation = scheduler_result.allocations[0]
        if allocation.scheduled_bytes <= 0:
            self.completed = True
            return self.snapshot(tick=tick, status="zero_allocation")

        transmission = transmit(tick=tick, allocation=allocation, channel=channel)
        self.rlc_queue = apply_transmission_to_rlc(self.rlc_queue, transmission)
        ru_result = receive_radio(transmission)
        n3 = build_n3_result(apply_backhaul(forward_to_n3(ru_result, self.session)))
        n6 = forward_n6(forward_via_upf(n3, self.session, target=self.ue_request.target))
        delivered = deliver_to_data_network(n6)

        self.ticks_executed += 1
        self.cumulative_attempted_bytes += transmission.attempted_bytes
        self.cumulative_successful_bytes += delivered.delivered_bytes
        self.cumulative_failed_bytes += transmission.failed_bytes + n3.n3_loss_bytes + delivered.n6_loss_bytes
        self.cumulative_dropped_bytes += transmission.dropped_bytes
        self.cumulative_n3_loss_bytes += n3.n3_loss_bytes
        self.cumulative_n6_loss_bytes += delivered.n6_loss_bytes
        if self.rlc_queue.queued_bytes <= 0 and self.rlc_queue.retransmission_bytes <= 0:
            self.completed = True

        qos = calculate_qos(
            requested_bytes=self.traffic.total_bytes,
            transmission=transmission,
            n3=n3,
            n6=delivered,
            delay_budget_ms=self.qos_flow.packet_delay_budget_ms,
        )
        result = build_end_to_end_result(
            service_id=self.traffic.service_id,
            ue_id=self.ue_request.ue_id,
            target=self.ue_request.target,
            slice_id=self.slice_id,
            access_type=self.access.access_type,
            requested_bytes=self.traffic.total_bytes,
            delivered_bytes=min(self.traffic.total_bytes, self.cumulative_successful_bytes),
            qos=qos,
        )
        delivered_payload_bytes = min(self.traffic.total_bytes, self.cumulative_successful_bytes)
        dropped_bytes = self.cumulative_dropped_bytes + self.cumulative_n3_loss_bytes + self.cumulative_n6_loss_bytes
        remaining_payload_bytes = max(0, self.traffic.total_bytes - delivered_payload_bytes - dropped_bytes)
        remaining_queue_bytes = self.rlc_queue.queued_bytes + self.rlc_queue.retransmission_bytes
        state = {
            "mode": "tick",
            "status": "completed" if self.completed else "running",
            "tick": tick,
            "ticks_executed": self.ticks_executed,
            "result": asdict(result),
            "gnb": asdict(self.gnb),
            "ue_request": asdict(self.ue_request),
            "access": asdict(self.access),
            "session": asdict(self.session),
            "traffic": asdict(self.traffic),
            "qos_flow": asdict(self.qos_flow),
            "sdap_output": asdict(self.sdap_output),
            "pdcp_batch": asdict(self.pdcp_batch),
            "drb": asdict(self.drb),
            "rlc_queue_after": asdict(self.rlc_queue),
            "channel": asdict(channel),
            "scheduler_request": asdict(scheduler_request),
            "scheduler_result": asdict(scheduler_result),
            "transmission": asdict(transmission),
            "n3": asdict(n3),
            "n6": asdict(delivered),
            "slice_usage": summarize_slice_usage(scheduler_result.allocations),
            "progress": {
                "requested_bytes": self.traffic.total_bytes,
                "delivered_bytes": delivered_payload_bytes,
                "remaining_payload_bytes": remaining_payload_bytes,
                "remaining_queue_bytes": remaining_queue_bytes,
                "completion_ratio": min(1.0, delivered_payload_bytes / self.traffic.total_bytes),
                "remaining_ratio": remaining_payload_bytes / self.traffic.total_bytes,
                "dropped_bytes": dropped_bytes,
            },
        }
        self.last_state = state
        return state

    def snapshot(self, *, tick: int, status: str | None = None) -> dict[str, object]:
        """Project implementation detail."""

        if self.last_state is not None:
            state = dict(self.last_state)
            state["tick"] = tick
            state["status"] = status or state.get("status", "running")
            return state
        return {
            "mode": "tick",
            "status": status or "initialized",
            "tick": tick,
            "ticks_executed": self.ticks_executed,
            "gnb": asdict(self.gnb),
            "ue_request": asdict(self.ue_request),
            "access": asdict(self.access),
            "session": asdict(self.session),
            "traffic": asdict(self.traffic),
            "qos_flow": asdict(self.qos_flow),
            "sdap_output": asdict(self.sdap_output),
            "pdcp_batch": asdict(self.pdcp_batch),
            "drb": asdict(self.drb),
            "rlc_queue_after": asdict(self.rlc_queue),
            "progress": {
                "requested_bytes": self.traffic.total_bytes,
                "delivered_bytes": min(self.traffic.total_bytes, self.cumulative_successful_bytes),
                "remaining_payload_bytes": max(
                    0,
                    self.traffic.total_bytes
                    - min(self.traffic.total_bytes, self.cumulative_successful_bytes)
                    - self.cumulative_dropped_bytes
                    - self.cumulative_n3_loss_bytes
                    - self.cumulative_n6_loss_bytes,
                ),
                "remaining_queue_bytes": (
                    self.rlc_queue.queued_bytes + self.rlc_queue.retransmission_bytes
                ),
                "completion_ratio": 0.0,
                "remaining_ratio": 1.0,
                "dropped_bytes": (
                    self.cumulative_dropped_bytes
                    + self.cumulative_n3_loss_bytes
                    + self.cumulative_n6_loss_bytes
                ),
            },
        }
