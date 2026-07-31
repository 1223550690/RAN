from __future__ import annotations

from dataclasses import asdict

from ran.access import select_access
from ran.contracts import AgentIntent, Position
from ran.core import deliver_to_data_network, establish_pdu_session, forward_via_upf, register_ue
from ran.gnb import build_scheduler_request, forward_to_n3, receive_radio
from ran.metrics import build_end_to_end_result, calculate_qos, summarize_slice_usage
from ran.protocol import apply_transmission_to_rlc, build_pdcp_batch, build_rlc_queue, map_qos_flow_to_drb
from ran.qos import build_qos_flow
from ran.radio import estimate_channel, load_gnb_site_from_scene, transmit
from ran.scheduler import PythonBaselineScheduler
from ran.slicing import classify_slice
from ran.slicing.controller import update_slice_policies
from ran.traffic import build_ip_traffic
from ran.transport import apply_backhaul, build_n3_result, forward_n6
from ran.ue import build_demo_ue_state, build_ue_request


class RanUploadScenario:
    """Project implementation detail."""

    
    def __init__(self, scene, scheduler=None) -> None:
        self.scene = scene
        self.scheduler = scheduler or PythonBaselineScheduler()
        self.intents = [AgentIntent(
            agent_id="student_a",
            agent_pos=Position(520.0, 430.0),
            action="upload",
            target="youtube_server",
            content_type="video",
            size_bytes=100 * 1024 * 1024,
            requirement="uplink",
        ),AgentIntent(
            agent_id="student_b",
            agent_pos=Position(340.0, 300.0),
            action="upload",
            target="youtube_server",
            content_type="video",
            size_bytes=50 * 1024 * 1024,
            requirement="uplink",
        ),AgentIntent(
            agent_id="student_c",
            agent_pos=Position(200.0, 480.0),
            action="upload",
            target="youtube_server",
            content_type="video",
            size_bytes=75 * 1024 * 1024,
            requirement="uplink",),
            ]
        self.gnb = load_gnb_site_from_scene(scene)
        ue_ids = ["student_a_phone", "student_b_phone", "student_c_phone"]

        self.slice_policies = update_slice_policies()
        self.completed = False
        self.ticks_executed = 0
        self.cumulative_attempted_bytes = 0
        self.cumulative_successful_bytes = 0
        self.cumulative_failed_bytes = 0
        self.cumulative_dropped_bytes = 0
        self.cumulative_n3_loss_bytes = 0
        self.cumulative_n6_loss_bytes = 0
        self.last_states: dict[str, dict[str, object]] = {}
        users = self.buildStates(self.intents, ue_ids, self.gnb)
        self.users: dict[str, dict[str, object]] = users
        
        

    def step(self, tick: int) -> list[dict[str, object]]:
        """Project implementation detail."""
        # if self.completed:
        #     return self.snapshot(tick=tick, status="completed")
        rlc_queues, qos_flows, drbs, power_reports, requirements = [],[],[],[],[]
        channel_states = {}
        ue_allocations = {}
        for userKey in self.users:
            user = self.users[userKey]
            if user["status"] != "complete":
                rlc_queues.append(user["rlc_queue"])
                qos_flows.append(user["qos_flow"])
                drbs.append(user["drb"])
                channel = estimate_channel(tick=tick, scene=self.scene, ue_request=user["ue_request"], gnb=self.gnb)
                channel_states.update({channel.ue_id:channel})
                power_reports.append(self.last_states[userKey]["transmission"]["power_report"]) if tick !=1 else None
                requirements.append(user["requirement"])
            
        scheduler_request = build_scheduler_request(
                        tick=tick,  
                        total_prbs=self.gnb.total_prbs,
                        rlc_queues=rlc_queues,
                        qos_flows=qos_flows,
                        drbs=drbs,
                        channel_states=channel_states,
                        slice_policies=self.slice_policies,
                        power_report=power_reports,
                        requirements=requirements
                    )
        scheduler_result = self.scheduler.allocate(scheduler_request)
        if not scheduler_result.allocations:
                        self.completed = True
                        return self.snapshot(tick=tick, status="no_allocation")
        for userKey in self.users:
            user = self.users[userKey]
            if (user["status"] != "complete"):
                for allocation in scheduler_result.allocations:
                    ue_allocations.update({allocation.ue_id: allocation})
                transmission = transmit(tick=tick, allocation=ue_allocations[userKey], channel=channel_states[userKey], ue_state=user["ue_state"], gnb=self.gnb)
                user["rlc_queue"] = apply_transmission_to_rlc(user["rlc_queue"], transmission)
                ru_result = receive_radio(transmission)
                n3 = build_n3_result(apply_backhaul(forward_to_n3(ru_result, user["session"])))
                n6 = forward_n6(forward_via_upf(n3, user["session"], target=user["ue_request"].target))
                delivered = deliver_to_data_network(n6)
                if user["rlc_queue"].queued_bytes <= 0 and user["rlc_queue"].retransmission_bytes <= 0:
                            user["status"] = "complete"
                qos = calculate_qos(
                                requested_bytes=user["traffic"].total_bytes,
                                transmission=transmission,
                                n3=n3,
                                n6=delivered,
                                delay_budget_ms=user["qos_flow"].packet_delay_budget_ms,
                            )
                user["cumulative_attempted_bytes"]+= transmission.attempted_bytes
                user["cumulative_successful_bytes"]+= delivered.delivered_bytes
                user["cumulative_failed_bytes"] += transmission.failed_bytes + n3.n3_loss_bytes + delivered.n6_loss_bytes
                user["cumulative_dropped_bytes"] += transmission.dropped_bytes
                user["cumulative_n3_loss_bytes"] += n3.n3_loss_bytes
                user["cumulative_n6_loss_bytes"] += delivered.n6_loss_bytes
                result = build_end_to_end_result(
                                service_id=user["traffic"].service_id,
                                ue_id=user["ue_request"].ue_id,
                                target=user["ue_request"].target,
                                slice_id=user["slice_id"],
                                access_type=user["ue_access_value"].access_type,
                                requested_bytes=user["traffic"].total_bytes,
                                delivered_bytes=min(user["traffic"].total_bytes, user["cumulative_successful_bytes"]),
                                qos=qos,
                            )
                delivered_payload_bytes = min(user["traffic"].total_bytes, user["cumulative_successful_bytes"])
                dropped_bytes = user["cumulative_dropped_bytes"] +user["cumulative_n3_loss_bytes"]+ user["cumulative_n6_loss_bytes"]
                remaining_payload_bytes = max(0, user["traffic"].total_bytes - delivered_payload_bytes - dropped_bytes)
                remaining_queue_bytes = user["rlc_queue"].queued_bytes + user["rlc_queue"].retransmission_bytes
                if remaining_payload_bytes == 0:
                    user["status"] = "complete"

                agentState = {
                    "tick": tick,
                    "result": asdict(result),
                    "status": user["status"],
                    "ue_request": asdict(user["ue_request"]),
                    "access": asdict(user["ue_access_value"]),
                    "qos_flow": asdict(user["qos_flow"]),
                    "drb": asdict(user["drb"]),
                    "rlc_queue_after": asdict(user["rlc_queue"]),
                    "channel": asdict(channel_states[userKey]),
                    "transmission": asdict(transmission),
                    "n3": asdict(n3),
                    "n6": asdict(delivered),
                    "progress": {
                        "requested_bytes": user["traffic"].total_bytes,
                        "delivered_bytes": delivered_payload_bytes,
                        "remaining_payload_bytes": remaining_payload_bytes,
                        "remaining_queue_bytes": remaining_queue_bytes,
                        "completion_ratio": min(1.0, delivered_payload_bytes / user["traffic"].total_bytes),
                        "remaining_ratio": remaining_payload_bytes / user["traffic"].total_bytes,
                        "dropped_bytes": dropped_bytes,
                    },
                }
                self.last_states[userKey] = agentState
        
        self.ticks_executed += 1
        self.completed = True
        for userKey in self.users:
            user = self.users[userKey]
            if user["status"] != "complete":
                 self.completed = False
        overallState = {
            "mode": "tick",
            "status": "complete" if self.completed else "running",
            "tick": tick,
            "ticks_executed": self.ticks_executed,
            "gnb": asdict(self.gnb),
            "scheduler_request": asdict(scheduler_request),
            "scheduler_result": asdict(scheduler_result),
            "slice_usage": summarize_slice_usage(scheduler_result.allocations),
            "agentStates": self.last_states,
        }
        self.last_state = overallState
        
        return overallState

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
                "remaining_queue_bytes": self.rlc_queue.queued_bytes + self.rlc_queue.retransmission_bytes,
                "completion_ratio": 0.0,
                "remaining_ratio": 1.0,
                "dropped_bytes": self.cumulative_dropped_bytes + self.cumulative_n3_loss_bytes + self.cumulative_n6_loss_bytes,
            },
        }

    def buildStates(self, intents:list[AgentIntent], ue_ids:list[str], gnb) -> dict[str, dict[str, object]]:
        
        i = 0
        users = {}
        for intent in intents:
            
            ue_state = register_ue(build_demo_ue_state(
                agent_id=intent.agent_id,
                ue_id=ue_ids[i] if ue_ids[i] else "placeholder",
                position=intent.agent_pos,
            ))
            ue_request = build_ue_request(intent, ue_id=ue_state.ue_id, selected_access="5g")
            ue_access = select_access(ue_request, gnb)
            slice_id = classify_slice(ue_request.service_type)
            session = establish_pdu_session(ue_state, ue_request, slice_id=slice_id)
            traffic = build_ip_traffic(ue_request, session)
            qos_flow = build_qos_flow(ue_request, session)
            drb = map_qos_flow_to_drb(qos_flow, ue_request)
            pdcp_batch = build_pdcp_batch(traffic, drb)
            rlc_queue = build_rlc_queue(pdcp_batch, drb)
            self.last_states.update({ue_request.ue_id:None})
            i += 1
            users.update({ue_request.ue_id:{"ue_state": ue_state,
                        "ue_request": ue_request,
                        "ue_access_value": ue_access,
                        "slice_id": slice_id,
                        "session": session,
                        "traffic": traffic,
                        "qos_flow": qos_flow,
                        "drb": drb,
                        "pdcp_batch": pdcp_batch,
                        "rlc_queue": rlc_queue,
                        "status": "running",
                        "requirement": intent.requirement,
                        "cumulative_attempted_bytes": 0,
                        "cumulative_successful_bytes": 0,
                        "cumulative_failed_bytes": 0,
                        "cumulative_dropped_bytes":0,
                        "cumulative_n3_loss_bytes":0,
                        "cumulative_n6_loss_bytes":0
                        }})
        return users