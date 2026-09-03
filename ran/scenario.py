from __future__ import annotations

from dataclasses import asdict, replace
from typing import Any
import random

from ran.access import select_access
from ran.contracts import (
    CONTRACT_VERSION,
    AgentIntent,
    AgentStateSnapshot,
    Position,
    QosMetrics,
    RlcQueue,
    Drb,
    UERequest,
    N3ForwardingResult,
    N6DeliveryResult,
    TransmissionResult,
    Signal,
    UEState, 
    revertIp,
    convertIp,
    ApplicationManager,
)
from ran.core import Amf, Upf, deliver_to_data_network, establish_pdu_session, forward_via_upf, register_ue, SessionManagementFunction
from ran.gnb import build_scheduler_request, forward_to_n3, receive_radio
from ran.metrics import build_end_to_end_result, calculate_qos, summarize_slice_usage
from ran.orchestration import (
    AgentContext,
    AgentStateProvider,
    IntentContext,
    MockAgentStateProvider,
    RanScenarioDefinition,
    ServiceContext,
    UeContext,
    build_default_three_agent_definition,
    ServiceContent,
)
from ran.protocol import (
    PdcpEntity,
    RlcEntity,
    apply_transmission_to_rlc,
    build_pdcp_batch,
    build_rlc_queue,
    map_qos_flow_to_drb,
)
from ran.qos import build_qos_flow
from ran.radio import estimate_channel, load_gnb_site_from_scene, transmit
from ran.scheduler import JavaSchedulerAdapter
from ran.slicing import classify_slice
from ran.slicing.controller import update_slice_policies
from ran.traffic import build_ip_traffic, IPPacketFactory, EndpointProfile
from ran.transport import apply_backhaul, build_n3_result, forward_n6
from ran.ue import build_demo_ue_state, build_ue_request


TERMINAL_SERVICE_STATUSES = {"COMPLETED", "FAILED"}



class MultiAgentRanScenario:
    """RAN scenario orchestrator for a fixed Agent set; protocol details are refined by the individual modules."""

    def __init__(
        self,
        scene,
        scheduler=None,
        *,
        definition: RanScenarioDefinition | None = None,
        agent_state_provider: AgentStateProvider | None = None,
        tick_ms: float = 1000.0,
        n3_bandwidth_mbps: float | None = None,
        max_waiting_ticks: int = 600,
    ) -> None:
        
        self.scene = scene
        self.scheduler = scheduler or JavaSchedulerAdapter()
        self.tick_ms = float(tick_ms)
        self.max_waiting_ticks = int(max_waiting_ticks)
        self.definition = definition or build_default_three_agent_definition()
        self.simulation_id = self.definition.simulation_id
        self.agent_count = self.definition.agent_count
        self.agent_ids = tuple(item.agent_id for item in self.definition.agents)
        self.agent_state_provider = agent_state_provider or MockAgentStateProvider(self.definition)
        self.gnb = load_gnb_site_from_scene(scene)
        self.amf = Amf()
        self.upf = Upf(n3_bandwidth_mbps=n3_bandwidth_mbps)
        self.slice_policies = update_slice_policies()
        self._ensure_hybrid_ckm()
        self.agents: dict[str, AgentContext] = {}
        self.intents: dict[str, IntentContext] = {}
        self.transitSignals: list[Signal]=[]
        self.ues: dict[str, UeContext] = {}
        self.services: dict[str, ServiceContext] = {}
        self.service_order: list[str] = []
        self.completed = False
        self.ticks_executed = 0
        self.servers = self.definition.servers
        self.last_state: dict[str, object] | None = None
        self.protocolStack = True
        initial_states = self._read_agent_states(tick=0)
        endpoints = []
        for serverId in self.servers:
            server = self.servers[serverId]
            for protocol in server.protocols:
                endpoints.append(EndpointProfile(
                    target=server.name + " "+protocol,
                    dnn=server.dnn,
                    ip=server.address,
                    protocol=protocol,
                    port=server.port,
                    service_types=server.service_types,
                ))
        self.factory = IPPacketFactory(endpoints)
        self.smf = SessionManagementFunction()
        self.ipByUe = {}
        self.ueByIp = {}
        self.serversByIp = {}
        self.ipByServers = {}
        self._build_contexts(initial_states)


    def _ensure_hybrid_ckm(self) -> None:
        """Hybrid channel mode: build (or load from cache) a hybrid CKM at simulation startup and attach it to scene.

        When the build fails or is disabled, scene.ckm stays None and estimate_channel falls back automatically.
        Set the environment variable RAN_DISABLE_CKM=1 to skip the build (for test environments).
        """

        import os

        if os.environ.get("RAN_DISABLE_CKM") == "1":
            return
        try:
            from ran.radio.channel_policy import load_channel_model_policy

            policy = load_channel_model_policy(str(getattr(self.scene, "node_id", "")))
        except Exception:
            policy = None
        if policy is None or not policy.is_hybrid:
            return
        try:
            from ran.ckm import CkmConfig, build_hybrid_ckm

            config = CkmConfig.from_dict(policy.ckm_config)
            ckm = build_hybrid_ckm(
                scene=self.scene,
                gnb=self.gnb,
                policy=policy,
                ckm_config=config,
            )
            if ckm is not None:
                self.scene.ckm = ckm
                print(
                    f"[ckm] hybrid CKM ready: cells={len(ckm.cells)} "
                    f"refs={ckm.model_metadata.get('reference_count')} "
                    f"build={ckm.model_metadata.get('build_seconds')}s",
                    flush=True,
                )
        except Exception as exc:  # CKM failure must not block the simulation (fall back to shadow)
            print(f"[ckm] hybrid CKM build failed, falling back to shadow: {exc}", file=sys.stderr, flush=True)

    
    def step(self, tick: int) -> dict[str, object]:
        """Advance one tick: aggregate all active queues, schedule once, then execute per service."""
        # if self.completed:
        #     # Even with no active services, keep refreshing the RAN-side Agent copies to avoid stale nested snapshots
        #     # (the completed fast path used to skip re-reading Agent coordinates, so the preview page
        #     #  saw a frozen movement phase when reading this copy, until the first intent submission reactivated the scenario)
        #     self._update_agent_states(tick)
        #     return self.snapshot(tick=tick, status="completed")
        self._update_agent_states(tick)
        active_services = [
            self.services[service_id]
            for service_id in self.service_order
            if self.services[service_id].status not in TERMINAL_SERVICE_STATUSES
        ]
        # if not active_services:
        #     self.completed = True
        #     return self.snapshot(tick=tick, status="completed")

        # N3 flow: UPF buffer → gNB DL queue (downlink; instantaneous arrival by default, bounded by n3 bandwidth).
        # Placed before scheduling so this scheduling window can see downlink data that has reached the gNB.
        for service in active_services:
            if service.dl_queue is not None:
                dl_tunnel = self.upf.tunnel_of(service.ue_id, service.session.pdu_session_id, "DL")
                if dl_tunnel is not None:
                    n3_tx = self.upf.forward_to_gnb(dl_tunnel, tick_ms=self.tick_ms)
                    if n3_tx > 0:
                        if service.rlc is not None:
                            service.rlc.enqueue_bytes(n3_tx)
                        else:
                            service.dl_queue.queued_bytes += n3_tx
                    service.upf_buffered_bytes = self.upf.buffered_bytes(service.ue_id, service.session.pdu_session_id)
                    service.n3_gtp_overhead_bytes = dl_tunnel.overhead_total_bytes
        # UL inflow: entity pipeline PDCP→RLC enqueue (before scheduling, so this tick's new data is visible)
        for service in active_services:
            if service.rlc is not None and service.dl_queue is None:
                service.rlc.enqueue(service.pdcp.process(service.traffic, tick=tick))
        #Allow signals to propagate
        self.updateSignals(tick)
        
        for signal in self.transitSignals:
            if signal.arrived and signal.direction == "DL":
                self.receiveDownlinkMessage(signal)
            elif signal.arrived and signal.direction == "UL":
                self.receiveUplinkMessage(signal)

        newSignals = []
        for signal in self.transitSignals:
            if signal.arrived != True:
                newSignals.append(signal)
        self.transitSignals = newSignals

        channel_by_service = {}
        channel_by_link = {}
        
        for ue in self.ues:
            state = self.ues[ue].state
            for message in state.applicationLayer.messageBuffer:
                self.transitSignals.append(Signal(
                    tickSent = tick,
                    estimatedArrivalTick=tick+11,
                    arrived=False,
                    direction="UL",
                    ticksInTransit = 0,
                    payload=message,
                ))
            state.applicationLayer.messageBuffer = []
        for server in self.servers:
            server = self.servers[server]
            for message in server.applicationLayer.messageBuffer:
                self.transitSignals.append(Signal(
                    tickSent = tick,
                    estimatedArrivalTick=tick+11,
                    arrived=False,
                    direction="DL",
                    ticksInTransit = 0,
                    payload=message,
                ))
            server.applicationLayer.messageBuffer = []
        
        for ue in self.ues:
            state = self.ues[ue].state
            state.applicationLayer.updateManagers()
        for server in self.servers:
            server = self.servers[server]
            server.applicationLayer.updateManagers()
        
        for service in active_services:
            channel = estimate_channel(
                tick=tick,
                scene=self.scene,
                ue_request=service.ue_request,
                gnb=self.gnb,
            )
            channel_by_service[service.service_instance_id] = channel
            channel_by_link[(channel.ue_id, channel.gnb_id, channel.direction)] = channel
        scheduler_request = build_scheduler_request(
            simulation_id=self.simulation_id,
            tick=tick,
            gnb_id=self.gnb.gnb_id,
            total_prbs=self.gnb.total_prbs,
            rlc_queues=[self._rlc_queue_state(service) for service in active_services],
            qos_flows=[service.qos_flow for service in active_services],
            drbs=[service.drb for service in active_services],
            channel_states=list(channel_by_link.values()),
            slice_policies=self.slice_policies,
            slot_ms=self.tick_ms,
        )
        scheduler_result = self.scheduler.allocate(scheduler_request)
        # self._validate_scheduler_result(scheduler_request, scheduler_result)
        allocation_by_bearer = {
            (allocation.ue_id, allocation.drb_id, allocation.direction): allocation
            for allocation in scheduler_result.allocations
        }

        service_states: list[dict[str, object]] = []
        for service_id in self.service_order:
            service = self.services[service_id]
            if service.status in TERMINAL_SERVICE_STATUSES:
                service_states.append(self._reuse_terminal_state(service, tick))
                continue

            allocation = allocation_by_bearer.get(
                (service.ue_id, service.drb.drb_id, service.ue_request.direction)
            )
            channel = channel_by_service[service.service_instance_id]
            if allocation is None or allocation.scheduled_bytes <= 0:
                service.waiting_ticks += 1
                if service.waiting_ticks >= self.max_waiting_ticks:
                    # Service failure determination (0608 requirement): long-term lack of allocation (poor channel/starvation) → FAILED
                    service.status = "FAILED"
                    service_states.append(self._build_waiting_service_state(service, channel, tick))
                    continue
                service.status = "WAITING_FOR_ALLOCATION"
                service_states.append(self._build_waiting_service_state(service, channel, tick))
                continue
            service.waiting_ticks = 0  # allocation received, reset waiting counter

            # Minimal RLC grant mock: currently just truncated by queue bytes; to be replaced by a real segment list.
            if service.rlc is not None:
                actual_grant_bytes = min(
                    allocation.scheduled_bytes,
                    service.rlc.queued_bytes + service.rlc.retransmission_bytes,
                )
            else:
                grant_queue = service.dl_queue if service.dl_queue is not None else service.rlc_queue
                actual_grant_bytes = min(
                    allocation.scheduled_bytes,
                    grant_queue.queued_bytes + grant_queue.retransmission_bytes,
                )
            executed_allocation = replace(allocation, scheduled_bytes=actual_grant_bytes)
            service_states.append(
                self._execute_service_tick(service, channel, executed_allocation, tick)
            )


        for server in self.servers:
                    self.servers[server].prepareBuffer()
                    if self.servers[server].requiresDL:
                        for message in self.servers[server].bufferOut:
                            recipient = self.ueByIp[message.recipient] if message.recipient in self.ueByIp else message.recipient
                            request = UERequest(
                                ue_id=recipient,
                                agent_id=f"agent_{recipient}",
                                position=Position(10.0, 20.0),
                                direction="DL", 
                                selected_access="5g",
                                access_type="3gpp",
                                target=self.servers[server].address,
                                dnn="internet",
                                pdu_session_type="IPv4",
                                service_type=message.service_type,
                                requested_payload_bytes=message.size,
                                qos_hint={},
                                )
                            state = UEState(
                                ue_id=request.ue_id,
                                agent_id=f"agent_{request.ue_id}",
                                position=Position(10.0, 20.0),
                                rm_state="REGISTERED",
                                cm_state="CONNECTED",
                                rrc_state="CONNECTED",
                                allowed_slices=["embb", "urllc", "mmtc"],
                                signalBuffer = None,
                                applicationLayer = ApplicationManager(),
                            )
                            
                            access = select_access(request, self.gnb)
                            session = self.smf.establish(ue=state, request=request, slice_id="embb")
                            traffic = self.factory.build(request, session)
                            traffic.dst_ip = self.ipByUe[message.recipient]
                            qos_flow = build_qos_flow(request, session)
                            drb = map_qos_flow_to_drb(qos_flow, request)
                            pdcp_batch = build_pdcp_batch(replace(traffic), drb)
                            pdcp_entity = PdcpEntity(
                                        drb_id=drb.drb_id,
                                        qfi=drb.qfi,
                                        slice_id=drb.slice_id,
                                    )
                            rlc_entity = RlcEntity(
                                        ue_id=drb.ue_id,
                                        drb_id=drb.drb_id,
                                        qfi=drb.qfi,
                                        slice_id=drb.slice_id,
                                        direction=drb.direction,
                                        mode=drb.rlc_mode,
                                    )
                            tunnel = self.upf.create_tunnel(state.ue_id, session.pdu_session_id, request.direction)
                            self.upf.receive_from_dn(state.ue_id, session.pdu_session_id, pdcp_batch.output_bytes)
                            dl_queue = replace(build_rlc_queue(pdcp_batch, drb), queued_bytes=0, retransmission_bytes=0)
                            rlc_queue = replace(rlc_queue_placeholder(request, drb))
                            service = ServiceContext(
                                service_instance_id="gnb" +str(random.randint(0,1000)),
                                intent_id="gnb_dl"+str(random.randint(0,1000)),
                                intent_type=message.service_type,
                                agent_id=request.agent_id,
                                ue_id=request.ue_id,
                                ue_request=request,
                                access=access,
                                slice_id="embb",
                                session=session,
                                traffic=traffic,
                                qos_flow=qos_flow,
                                pdcp=pdcp_entity,
                                rlc=None,
                                drb=drb,
                                pdcp_batch=pdcp_batch,
                                rlc_queue=rlc_queue,
                                dl_queue=dl_queue,
                                upf_buffered_bytes=self.upf.buffered_bytes(state.ue_id, session.pdu_session_id),
                                n3_tunnel_id=tunnel.tunnel_id,
                                status="ACTIVE",
                                content= message.content,
                            )
                            dataString = self.servers[server].applicationLayer.prepareString(str(message.sender) + ':' + message.service_type + ':' + message.content + ':' + str(message.size))
                            self.servers[server].applicationLayer.send(traffic.dst_ip, self.servers[server].port,"TCP", dataString, self.servers[server].port, self.servers[server].address)
                            self.services[service.service_instance_id] = service
                            self.service_order.append(service.service_instance_id)
                        self.servers[server].clearBuffer()
        self.ticks_executed += 1
        self._refresh_lifecycle_states(tick)
        self.completed = all(
            service.status in TERMINAL_SERVICE_STATUSES for service in self.services.values()
        )
        if self.completed:
            for signal in self.transitSignals:
                if signal.arrived == False:
                    self.completed = False
                    break
        state = self._compose_state(
            tick=tick,
            status="completed" if self.completed else "running",
            service_states=service_states,
            scheduler_request=asdict(scheduler_request),
            scheduler_result=asdict(scheduler_result),
            slice_usage=summarize_slice_usage(scheduler_result.allocations),
        )
        self.last_state = state
        
        return state


    def updateSignals(self, tick):
        for signal in self.transitSignals:
            signal.ticksInTransit += 1
            if(signal.estimatedArrivalTick == tick):
                signal.arrived = True

    def receiveUplinkMessage(self, signal):
        #Triggers backhaul and stores data for future downlink to UEs
        sender = signal.payload[96:128]
        destination = signal.payload[128:160]
        destination = revertIp(destination)
        self.servers[destination].receive(signal)
        return 0

    def receiveDownlinkMessage(self, signal):
        recieverUe = signal.payload[128:160]
        recieverUe = self.ueByIp[revertIp(recieverUe)]
        sender = signal.payload[96:128]
        sender = revertIp(sender)
        if recieverUe in self.ues:
            self.ues[recieverUe].state.receive(signal)
        return 0
    # ------------------------------------------------------------- Entity pipeline helpers (xizhe)

    def _rlc_queue_state(self, service) -> RlcQueue:
        """Entity pipeline: return the RLC entity queue state; the functional-compatible path returns the original queue."""

        rlc = getattr(service, "rlc", None)
        if rlc is not None:
            return rlc.to_queue_state()
        if service.dl_queue is not None:
            return service.dl_queue
        return service.rlc_queue

    def _queue_drained(self, service) -> bool:
        """Queue drained determination (entity includes inflight; functional includes queued/retransmission)."""

        rlc = getattr(service, "rlc", None)
        if rlc is not None:
            return (
                rlc.queued_bytes <= 0
                and rlc.retransmission_bytes <= 0
                and rlc.inflight_new_bytes <= 0
                and rlc.inflight_retx_bytes <= 0
            )
        if service.dl_queue is not None:
            return service.dl_queue.queued_bytes <= 0 and service.dl_queue.retransmission_bytes <= 0
        return service.rlc_queue.queued_bytes <= 0 and service.rlc_queue.retransmission_bytes <= 0

    def _execute_rlc_entity_tick(self, service, channel, allocation, tick: int) -> TransmissionResult:
        """Entity pipeline single tick: on_grant segmentation → PHY transmission → on_transmission_result feedback."""

        grant_result = service.rlc.on_grant(allocation)
        actual = replace(allocation, scheduled_bytes=grant_result.actual_sent_bytes)
        transmission = transmit(
            tick=tick,
            allocation=actual,
            channel=channel,
            rlc_mode=service.rlc.mode,
        )
        service.rlc.on_transmission_result(transmission)
        return transmission

    def get_agent_states(self, *, tick: int) -> list[dict[str, object]]:
        """Unified state interface exposing mock/real AgentStateProvider."""

        states = self._read_agent_states(tick)
        return [asdict(state) for state in states]

    def snapshot(self, *, tick: int, status: str | None = None) -> dict[str, object]:
        """Return a snapshot of the current scenario without advancing protocol state."""

        if self.last_state is not None:
            state = dict(self.last_state)
            state["tick"] = tick
            state["status"] = status or str(state.get("status", "running"))
            return state

        service_states = [self._build_initial_service_state(self.services[item]) for item in self.service_order]
        return self._compose_state(
            tick=tick,
            status=status or "initialized",
            service_states=service_states,
            scheduler_request={},
            scheduler_result={"allocations": []},
            slice_usage={},
        )

    def _build_contexts(self, initial_states: list[AgentStateSnapshot]) -> None:
        for server in self.definition.servers:
                    self.serversByIp.update({self.servers[server].address: self.servers[server]})
                    self.ipByServers.update({self.servers[server].name: self.servers[server].address})
        state_by_agent = {state.agent_id: state for state in initial_states}
        for index, item in enumerate(self.definition.agents):
            agent_state = state_by_agent[item.agent_id]
            self._register_ue(item, agent_state)
            if item.intent is None:
                # No initial intent: only register the UE; services are submitted dynamically by the runtime via submit_intent.
                self.agents[item.agent_id] = AgentContext(
                    agent_id=item.agent_id,
                    state=agent_state,
                    intent_ids=[],
                    ue_ids=[item.ue_id],
                )
                continue
            self._create_service(item, item.intent, index)
        

    def _register_ue(self, item, agent_state) -> None:
        """Register and store the Agent's UE control plane context. Keeps the existing context when the same UE is registered again."""

        if item.ue_id in self.ues:
            return
        ue_state = self.amf.register_ue(
            build_demo_ue_state(
                agent_id=item.agent_id,
                ue_id=item.ue_id,
                position=agent_state.position,
            )
        )
        self.ues[item.ue_id] = UeContext(
            state=ue_state,
            active_service_ids=[],
        )

    def _create_service(self, item, intent: AgentIntent, index: int) -> str:
        """Build the full service context from an Intent and return the service_instance_id."""

        service_instance_id = f"service_{intent.intent_id}"
        ue_state = self.ues[item.ue_id].state
        ue_state.applicationLayer = ApplicationManager()
        ue_request = build_ue_request(
            intent,
            ue_id=ue_state.ue_id,
            service_instance_id=service_instance_id,
            selected_access=item.selected_access,
        )
        access = select_access(ue_request, self.gnb)
        slice_id = classify_slice(ue_request.service_type)
        session = establish_pdu_session(
            ue_state,
            ue_request,
            slice_id=slice_id,
            ue_ip=_mock_ue_ip(index),
        )
        traffic = build_ip_traffic(factory=self.factory, request=ue_request, session=session)
        self.ipByUe.update({ue_state.ue_id: traffic.src_ip})
        self.ueByIp.update({traffic.src_ip: ue_state.ue_id})
        qos_flow = build_qos_flow(ue_request, session)
        drb = map_qos_flow_to_drb(qos_flow, ue_request)
        # The functional batch is only for accounting/statistics; the entity pipeline consumes from the original traffic each tick.
        # Build the batch from a copy so traffic.remaining_bytes is not consumed, which would leave the UL entity
        # inflow empty (legacy of the entity switch: UL queue stays empty and never gets scheduled).
        pdcp_batch = build_pdcp_batch(replace(traffic), drb)
        is_downlink = ue_request.direction == "DL"
        # xizhe entity pipeline (PDCP/RLC entities; functional build_* kept as a compatibility accounting path)
        pdcp_entity = PdcpEntity(
            drb_id=drb.drb_id,
            qfi=drb.qfi,
            slice_id=drb.slice_id,
        )
        rlc_entity = RlcEntity(
            ue_id=drb.ue_id,
            drb_id=drb.drb_id,
            qfi=drb.qfi,
            slice_id=drb.slice_id,
            direction=drb.direction,
            mode=drb.rlc_mode,
        )
        # GTP-U tunnel (both UL/DL created; UL for N3 delivery accounting, DL for buffer-and-forward)
        tunnel = self.upf.create_tunnel(ue_state.ue_id, session.pdu_session_id, ue_request.direction)
        if is_downlink:
            # Downlink: DN data arrives at the UPF buffer via N6 (not lost while the UE is suspended);
            # each tick, N3 flow fills the gNB-side RLC queue (entity enqueue_bytes).
            # Note: buffer and queue use the same accounting (pdcp_batch.output_bytes),
            # and the initial queue is emptied (all data sits in the UPF buffer) to avoid double enqueueing.
            self.upf.receive_from_dn(ue_state.ue_id, session.pdu_session_id, pdcp_batch.output_bytes)
            dl_queue = replace(build_rlc_queue(pdcp_batch, drb), queued_bytes=0, retransmission_bytes=0)
            rlc_queue = replace(rlc_queue_placeholder(ue_request, drb))
        else:
            dl_queue = None
            rlc_queue = build_rlc_queue(pdcp_batch, drb)

        # RRC setup: the service needs a radio bearer → IDLE/INACTIVE → CONNECTED.
        self.amf.establish_rrc(ue_state)
        content = ue_state.applicationLayer.prepareIntent(intent, traffic.dst_ip, traffic.src_ip, self.serversByIp, traffic.protocol)
        agent_context = self.agents.get(item.agent_id)
        if agent_context is None:
            # Theoretically unreachable: _build_contexts always registers AgentContext first; this fallback guards the invariant.
            agent_context = AgentContext(
                agent_id=item.agent_id,
                state=AgentStateSnapshot(
                    agent_id=item.agent_id,
                    tick=0,
                    position=ue_state.position,
                    status="READY",
                ),
                intent_ids=[],
                ue_ids=[item.ue_id],
            )
            self.agents[item.agent_id] = agent_context
        agent_context.intent_ids.append(intent.intent_id)
        self.intents[intent.intent_id] = IntentContext(
            intent=intent,
            status="ACTIVE",
            service_instance_ids=[service_instance_id],
        )
        ue_context = self.ues[item.ue_id]
        ue_context.active_service_ids.append(service_instance_id)
        self.services[service_instance_id] = ServiceContext(
            service_instance_id=service_instance_id,
            intent_id=intent.intent_id,
            intent_type=intent.service_type,
            agent_id=item.agent_id,
            ue_id=item.ue_id,
            ue_request=ue_request,
            access=access,
            slice_id=slice_id,
            session=session,
            traffic=traffic,
            qos_flow=qos_flow,
            pdcp=pdcp_entity,
            rlc=rlc_entity,
            drb=drb,
            pdcp_batch=pdcp_batch,
            rlc_queue=rlc_queue,
            dl_queue=dl_queue,
            upf_buffered_bytes=self.upf.buffered_bytes(ue_state.ue_id, session.pdu_session_id),
            n3_tunnel_id=tunnel.tunnel_id,
            status="ACTIVE",
            content= content
        )
        self.service_order.append(service_instance_id)
        return service_instance_id

    def submit_intent(self, intent: AgentIntent, *, selected_access: str = "5g") -> str:
        """Submit a new service intent at runtime and return the service_instance_id.

        Validation:
        - agent_id must belong to the Agent set frozen at scenario setup.
        - intent_id must be globally unique.
        - requested_payload_bytes must be positive.
        If the scenario had previously completed, submission reactivates the step loop.
        """

        if intent.agent_id not in self.agent_ids:
            raise ValueError(
                f"Intent {intent.intent_id!r} references unknown agent {intent.agent_id!r}; "
                "the Agent set is frozen at scenario creation"
            )
        if intent.intent_id in self.intents:
            raise ValueError(f"Intent id {intent.intent_id!r} already exists in this scenario")
        if intent.requested_payload_bytes <= 0:
            raise ValueError(f"Intent {intent.intent_id!r} must request positive payload bytes")

        item = next(
            item for item in self.definition.agents if item.agent_id == intent.agent_id
        )
        item = replace(item, selected_access=selected_access)  # type: ignore[arg-type]
        if self.completed:
            self.completed = False
        return self._create_service(item, intent, self._next_service_index())

    def _next_service_index(self) -> int:
        """Allocate a stable, unique UE IPv4 index for dynamically submitted services."""

        index = getattr(self, "_service_index_counter", len(self.service_order))
        self._service_index_counter = index + 1
        return index

    def _execute_service_tick(self, service, channel, allocation, tick: int) -> dict[str, object]:
        service.status = "ACTIVE"
        if service.dl_queue is not None:
            return self._execute_downlink_tick(service, channel, allocation, tick)
        if service.rlc is not None:
            # xizhe entity pipeline: on_grant segmentation → PHY → on_transmission_result
            transmission = self._execute_rlc_entity_tick(service, channel, allocation, tick)
        else:
            transmission = transmit(
                tick=tick,
                allocation=allocation,
                channel=channel,
                rlc_mode=service.rlc_queue.rlc_mode,
            )
            service.rlc_queue = apply_transmission_to_rlc(service.rlc_queue, transmission)
        
        ru_result = receive_radio(transmission)
        n3 = build_n3_result(apply_backhaul(forward_to_n3(ru_result, service.session)))
        # Uplink via the UPF entity (N3 arrival → N6 delivery to DN; with GTP-U tunnel overhead accounting)
        n6 = forward_n6(self.upf.forward_to_dn(n3, service.session, target=service.ue_request.target))
        ul_tunnel = self.upf.tunnel_of(service.ue_id, service.session.pdu_session_id, "UL")
        if ul_tunnel is not None:
            service.n3_gtp_overhead_bytes = ul_tunnel.overhead_total_bytes
        delivered = deliver_to_data_network(n6)

        counters = service.counters
        counters.attempted_protocol_bytes += transmission.attempted_bytes
        original_protocol_bytes = service.pdcp_batch.output_bytes
        remaining_protocol_bytes = max(
            0,
            original_protocol_bytes
            - counters.delivered_protocol_bytes
            - counters.permanently_dropped_protocol_bytes,
        )
        delivered_protocol_this_tick = min(remaining_protocol_bytes, delivered.delivered_bytes)
        counters.delivered_protocol_bytes += delivered_protocol_this_tick
        remaining_protocol_bytes -= delivered_protocol_this_tick
        dropped_protocol_this_tick = min(
            remaining_protocol_bytes,
            transmission.dropped_bytes + n3.n3_loss_bytes + delivered.n6_loss_bytes,
        )
        counters.permanently_dropped_protocol_bytes += dropped_protocol_this_tick
        counters.n3_loss_bytes += n3.n3_loss_bytes
        counters.n6_loss_bytes += delivered.n6_loss_bytes
        self._update_payload_counters(service)

        if self._queue_drained(service):
            unresolved_protocol_bytes = max(
                0,
                original_protocol_bytes
                - counters.delivered_protocol_bytes
                - counters.permanently_dropped_protocol_bytes,
            )
            counters.permanently_dropped_protocol_bytes += unresolved_protocol_bytes
            self._update_payload_counters(service)
            service.status = "COMPLETED"
            self._maybe_suspend_rrc(service)

        qos = calculate_qos(
            requested_bytes=service.traffic.total_bytes,
            transmission=transmission,
            n3=n3,
            n6=delivered,
            delay_budget_ms=service.qos_flow.packet_delay_budget_ms,
        )
        result = build_end_to_end_result(
            service_id=service.service_instance_id,
            ue_id=service.ue_id,
            target=service.ue_request.target,
            slice_id=service.slice_id,
            access_type=service.access.access_type,
            requested_bytes=service.traffic.total_bytes,
            delivered_bytes=counters.delivered_payload_bytes,
            qos=qos,
        )
        state = self._service_state_base(service, tick)
        state.update(
            {
                "status": service.status,
                "result": asdict(result),
                "rlc_queue_after": asdict(self._rlc_queue_state(service)),
                "channel": asdict(channel),
                "allocation": asdict(allocation),
                "transmission": asdict(transmission),
                "n3": asdict(n3),
                "n6": asdict(delivered),
                "progress": self._service_progress(service),
            }
        )
        service.last_state = state
        return state

    def _execute_downlink_tick(self, service, channel, allocation, tick: int) -> dict[str, object]:
        """Downlink tick: DN-side data is delivered to the UE over the gNB radio link.

        Symmetric to uplink: successful transmission bytes = bytes received by the UE; completion = DL queue drained.
        N3/N6 are zero-value placeholders (data goes from DN directly to gNB, not via UE uplink forwarding).
        """

        if service.rlc is not None:
            # xizhe entity pipeline: on_grant segmentation → PHY → on_transmission_result
            transmission = self._execute_rlc_entity_tick(service, channel, allocation, tick)
        else:
            transmission = transmit(
                tick=tick,
                allocation=allocation,
                channel=channel,
                rlc_mode=service.dl_queue.rlc_mode,
            )
            service.dl_queue = apply_transmission_to_rlc(service.dl_queue, transmission)

        counters = service.counters
        counters.attempted_protocol_bytes += transmission.attempted_bytes
        original_protocol_bytes = service.pdcp_batch.output_bytes
        remaining_protocol_bytes = max(
            0,
            original_protocol_bytes
            - counters.delivered_protocol_bytes
            - counters.permanently_dropped_protocol_bytes,
        )
        delivered_protocol_this_tick = min(
            remaining_protocol_bytes, max(0, transmission.successful_bytes)
        )
        counters.delivered_protocol_bytes += delivered_protocol_this_tick
        counters.permanently_dropped_protocol_bytes += max(0, transmission.failed_bytes)
        self._update_payload_counters(service)

        if (
            self._queue_drained(service)
            and self.upf.buffered_bytes(service.ue_id, service.session.pdu_session_id) <= 0
        ):
            unresolved_protocol_bytes = max(
                0,
                original_protocol_bytes
                - counters.delivered_protocol_bytes
                - counters.permanently_dropped_protocol_bytes,
            )
            counters.permanently_dropped_protocol_bytes += unresolved_protocol_bytes
            self._update_payload_counters(service)
            service.status = "COMPLETED"
            self._maybe_suspend_rrc(service)


        n3 = N3ForwardingResult(
            tunnel_id=f"dl_{service.session.pdu_session_id}",
            teid=0,
            ue_id=service.ue_id,
            pdu_session_id=service.session.pdu_session_id,
            upf_id=service.session.upf_id,
            forwarded_bytes=0,
            n3_delay_ms=0.0,
            n3_loss_bytes=0,
        )
        delivered = N6DeliveryResult(
            dnn=service.ue_request.dnn,
            target=service.ue_request.target,
            delivered_bytes=0,
            n6_delay_ms=0.0,
            n6_loss_bytes=0,
        )
        qos = calculate_qos(
            requested_bytes=service.traffic.total_bytes,
            transmission=transmission,
            n3=n3,
            n6=delivered,
            delay_budget_ms=service.qos_flow.packet_delay_budget_ms,
        )
        result = build_end_to_end_result(
            service_id=service.service_instance_id,
            ue_id=service.ue_id,
            target=service.ue_request.target,
            slice_id=service.slice_id,
            access_type=service.access.access_type,
            requested_bytes=service.traffic.total_bytes,
            delivered_bytes=counters.delivered_payload_bytes,
            qos=qos,
        )
        state = self._service_state_base(service, tick)
        state.update(
            {
                "status": service.status,
                "result": asdict(result),
                "rlc_queue_after": asdict(self._rlc_queue_state(service)),
                "channel": asdict(channel),
                "allocation": asdict(allocation),
                "transmission": asdict(transmission),
                "n3": asdict(n3),
                "n6": asdict(delivered),
                "progress": self._service_progress(service),
            }
        )
        service.last_state = state
        return state

    def _maybe_suspend_rrc(self, service) -> None:
        """Suspend RRC when the UE has no active services: CONNECTED→INACTIVE (3GPP service-gap behavior)."""

        ue_context = self.ues.get(service.ue_id)
        if ue_context is None:
            return
        if any(
            self.services[service_id].status not in TERMINAL_SERVICE_STATUSES
            for service_id in ue_context.active_service_ids
        ):
            return
        self.amf.suspend_rrc(ue_context.state)

    def _build_waiting_service_state(self, service, channel, tick: int) -> dict[str, object]:
        state = self._service_state_base(service, tick)
        state.update(
            {
                "status": service.status,
                "result": self._result_snapshot(service, QosMetrics(0.0, 0.0, 0.0, True, False)),
                "rlc_queue_after": asdict(service.rlc_queue),
                "channel": asdict(channel),
                "allocation": {},
                "transmission": {},
                "n3": {},
                "n6": {},
                "progress": self._service_progress(service),
            }
        )
        service.last_state = state
        return state

    def _build_initial_service_state(self, service) -> dict[str, object]:
        state = self._service_state_base(service, tick=0)
        state.update(
            {
                "status": "INITIALIZING",
                "result": self._result_snapshot(service, QosMetrics(0.0, 0.0, 0.0, False, False)),
                "rlc_queue_after": asdict(service.rlc_queue),
                "channel": {},
                "allocation": {},
                "transmission": {},
                "n3": {},
                "n6": {},
                "progress": self._service_progress(service),
            }
        )
        return state

    def _result_snapshot(self, service, qos: QosMetrics) -> dict[str, object]:
        result = build_end_to_end_result(
            service_id=service.service_instance_id,
            ue_id=service.ue_id,
            target=service.ue_request.target,
            slice_id=service.slice_id,
            access_type=service.access.access_type,
            requested_bytes=service.traffic.total_bytes,
            delivered_bytes=service.counters.delivered_payload_bytes,
            qos=qos,
        )
        return asdict(result)

    def _reuse_terminal_state(self, service, tick: int) -> dict[str, object]:
        if service.last_state is None:
            return self._build_initial_service_state(service)
        state = dict(service.last_state)
        state["tick"] = tick
        state["status"] = service.status
        state["allocation"] = {}
        state["transmission"] = {}
        state["n3"] = {}
        state["n6"] = {}
        return state

    def _service_state_base(self, service, tick: int) -> dict[str, object]:
        dl_remaining = None
        if service.dl_queue is not None:
            rlc = getattr(service, "rlc", None)
            if rlc is not None:
                dl_remaining = (
                    rlc.queued_bytes
                    + rlc.retransmission_bytes
                    + rlc.inflight_new_bytes
                    + rlc.inflight_retx_bytes
                    + service.upf_buffered_bytes
                )
            else:
                dl_remaining = (
                    service.dl_queue.queued_bytes
                    + service.dl_queue.retransmission_bytes
                    + service.upf_buffered_bytes
                )
        return {
            "agent_id": service.agent_id,
            "intent_id": service.intent_id,
            "intent_type": service.intent_type,
            "service_instance_id": service.service_instance_id,
            "ue_id": service.ue_id,
            "tick": tick,
            "direction": service.ue_request.direction,
            "dl_remaining_queue_bytes": dl_remaining,
            "waiting_ticks": service.waiting_ticks,
            "upf_buffered_bytes": service.upf_buffered_bytes,
            "n3_tunnel_id": service.n3_tunnel_id,
            "n3_gtp_overhead_bytes": service.n3_gtp_overhead_bytes,
            "ue_request": asdict(service.ue_request),
            "access": asdict(service.access),
            "qos_flow": asdict(service.qos_flow),
            "drb": asdict(service.drb),
        }

    def _agent_state_with_cp(self, agent_id: str) -> dict[str, object]:
        """Agent snapshot + CM/RRC control plane state of the Agent's UE (for frontend display)."""

        snapshot = asdict(self.agents[agent_id].state)
        for ue_context in self.ues.values():
            if ue_context.state.agent_id == agent_id:
                snapshot["cm_state"] = ue_context.state.cm_state
                snapshot["rrc_state"] = ue_context.state.rrc_state
                break
        return snapshot

    def _congestion_metrics(self, service_states: list[dict[str, object]]) -> dict[str, object]:
        """Congestion metrics (0608 requirement: network congestion determination):
        prb_ratio=PRB utilization this tick; queue_bytes=total backlog of active queues."""

        total_prbs = float(getattr(self.gnb, "total_prbs", 106) or 106)
        allocated = 0
        queue_bytes = 0
        waiting = 0
        for state in service_states:
            allocation = state.get("allocation") or {}
            allocated += int(allocation.get("prbs", 0) or 0)
            rlc = state.get("rlc_queue_after") or {}
            queue_bytes += int(rlc.get("queued_bytes", 0) or 0) + int(rlc.get("retransmission_bytes", 0) or 0)
            waiting += int(state.get("waiting_ticks", 0) or 0)
        return {
            "prb_ratio": round(min(1.0, allocated / total_prbs), 4) if total_prbs else 0.0,
            "queue_bytes": queue_bytes,
            "waiting_ticks": waiting,
            "active_services": len(service_states),
        }

    def _compose_state(
        self,
        *,
        tick: int,
        status: str,
        service_states: list[dict[str, object]],
        scheduler_request: dict[str, object],
        scheduler_result: dict[str, object],
        slice_usage: dict[str, int],
    ) -> dict[str, object]:
        primary = service_states[0] if service_states else {}
        progress = self._aggregate_progress()
        state = {
            "contract_version": CONTRACT_VERSION,
            "mode": "tick",
            "simulation_id": self.simulation_id,
            "status": status,
            "tick": tick,
            "ticks_executed": self.ticks_executed,
            "agent_count": self.agent_count,
            "agent_states": [self._agent_state_with_cp(item) for item in self.agent_ids],
            "service_states": service_states,
            "results": [item["result"] for item in service_states],
            "gnb": asdict(self.gnb),
            "scheduler_request": scheduler_request,
            "scheduler_result": scheduler_result,
            "slice_usage": slice_usage,
            "congestion": self._congestion_metrics(service_states),
            "progress": progress,
            # Legacy preview compatibility: map only the first Service; future frontends should read service_states.
            "result": primary.get("result", {}),
            "ue_request": primary.get("ue_request", {}),
            "access": primary.get("access", {}),
            "qos_flow": primary.get("qos_flow", {}),
            "drb": primary.get("drb", {}),
            "rlc_queue_after": primary.get("rlc_queue_after", {}),
            "channel": primary.get("channel", {}),
            "transmission": primary.get("transmission", {}),
            "n3": primary.get("n3", {}),
            "n6": primary.get("n6", {}),
        }
        return state

    def _aggregate_progress(self) -> dict[str, object]:
        requested = sum(service.traffic.total_bytes for service in self.services.values())
        delivered = sum(service.counters.delivered_payload_bytes for service in self.services.values())
        dropped = sum(
            service.counters.permanently_dropped_payload_bytes for service in self.services.values()
        )
        remaining = max(0, requested - delivered - dropped)
        queue_bytes = sum(
            service.rlc_queue.queued_bytes + service.rlc_queue.retransmission_bytes
            for service in self.services.values()
        )
        return {
            "requested_bytes": requested,
            "delivered_bytes": delivered,
            "remaining_payload_bytes": remaining,
            "remaining_queue_bytes": queue_bytes,
            "completion_ratio": delivered / requested if requested else 1.0,
            "remaining_ratio": remaining / requested if requested else 0.0,
            "dropped_bytes": dropped,
        }

    def _service_progress(self, service) -> dict[str, object]:
        requested = service.traffic.total_bytes
        delivered = service.counters.delivered_payload_bytes
        dropped = service.counters.permanently_dropped_payload_bytes
        remaining = max(0, requested - delivered - dropped)
        queue = service.dl_queue if service.dl_queue is not None else service.rlc_queue
        return {
            "requested_bytes": requested,
            "delivered_bytes": delivered,
            "remaining_payload_bytes": remaining,
            "remaining_queue_bytes": queue.queued_bytes + queue.retransmission_bytes,
            "completion_ratio": delivered / requested if requested else 1.0,
            "remaining_ratio": remaining / requested if requested else 0.0,
            "dropped_bytes": dropped,
        }

    def _remaining_payload_bytes(self, service) -> int:
        return max(
            0,
            service.traffic.total_bytes
            - service.counters.delivered_payload_bytes
            - service.counters.permanently_dropped_payload_bytes,
        )

    @staticmethod
    def _update_payload_counters(service) -> None:
        """Map protocol results proportionally to the original PDCP batch, preventing headers from being counted as application payload."""

        counters = service.counters
        protocol_total = service.pdcp_batch.output_bytes
        payload_total = service.traffic.total_bytes
        if protocol_total <= 0:
            counters.delivered_payload_bytes = 0
            counters.permanently_dropped_payload_bytes = payload_total
            return

        counters.delivered_payload_bytes = min(
            payload_total,
            payload_total * counters.delivered_protocol_bytes // protocol_total,
        )
        accounted_protocol_bytes = (
            counters.delivered_protocol_bytes + counters.permanently_dropped_protocol_bytes
        )
        if accounted_protocol_bytes >= protocol_total:
            counters.permanently_dropped_payload_bytes = (
                payload_total - counters.delivered_payload_bytes
            )
        else:
            counters.permanently_dropped_payload_bytes = min(
                payload_total - counters.delivered_payload_bytes,
                payload_total * counters.permanently_dropped_protocol_bytes // protocol_total,
            )

    def _read_agent_states(self, tick: int) -> list[AgentStateSnapshot]:
        states = self.agent_state_provider.get_agent_states(tick=tick)
        state_ids = [state.agent_id for state in states]
        if len(state_ids) != len(set(state_ids)):
            raise ValueError("AgentStateProvider returned duplicate agent_id values")
        if set(state_ids) != set(self.agent_ids) or len(states) != self.agent_count:
            raise ValueError("AgentStateProvider must return the fixed Agent set defined at scenario creation")
        if any(state.tick != tick for state in states):
            raise ValueError("AgentStateProvider returned a snapshot for the wrong tick")
        return states

    def _update_agent_states(self, tick: int) -> None:
        for state in self._read_agent_states(tick):
            self.agents[state.agent_id].state = state
            for ue_id in self.agents[state.agent_id].ue_ids:
                self.ues[ue_id].state.position = state.position
            for service in self.services.values():
                if service.agent_id == state.agent_id:
                    service.ue_request.position = state.position

    def _refresh_lifecycle_states(self, tick: int) -> None:
        for intent_context in self.intents.values():
            statuses = [self.services[item].status for item in intent_context.service_instance_ids]
            intent_context.status = "COMPLETED" if all(
                item in TERMINAL_SERVICE_STATUSES for item in statuses
            ) else "ACTIVE"

        for ue_context in self.ues.values():
            ue_context.active_service_ids = [
                item
                for item in ue_context.active_service_ids
                if self.services[item].status not in TERMINAL_SERVICE_STATUSES
            ]

        for agent_context in self.agents.values():
            service_ids = [
                service_id
                for intent_id in agent_context.intent_ids
                for service_id in self.intents[intent_id].service_instance_ids
            ]
            if not service_ids:
                # No intents submitted (dynamic mode): do not derive lifecycle state; keep the provider state.
                continue
            derived_status = "COMPLETED" if all(
                self.services[item].status in TERMINAL_SERVICE_STATUSES for item in service_ids
            ) else "ACTIVE"
            agent_context.state = replace(
                agent_context.state,
                tick=tick,
                status=derived_status,
            )

    @staticmethod
    def _validate_scheduler_result(request, result) -> None:
        if result.contract_version != request.contract_version:
            raise ValueError("SchedulerResult contract_version does not match SchedulerRequest")
        if result.simulation_id != request.simulation_id:
            raise ValueError("SchedulerResult simulation_id does not match SchedulerRequest")
        if result.scheduler_request_id != request.scheduler_request_id or result.tick != request.tick:
            raise ValueError("SchedulerResult does not reference the current SchedulerRequest")

        queue_by_bearer = {
            (queue.ue_id, queue.drb_id, queue.direction): queue for queue in request.rlc_queues
        }
        seen = set()
        allocated_prbs = 0
        for allocation in result.allocations:
            key = (allocation.ue_id, allocation.drb_id, allocation.direction)
            if key in seen:
                raise ValueError(f"Scheduler returned duplicate allocation for bearer {key!r}")
            if key not in queue_by_bearer:
                raise ValueError(f"Scheduler returned allocation for unknown bearer {key!r}")
            if allocation.prbs < 0 or allocation.scheduled_bytes < 0:
                raise ValueError("Scheduler returned a negative PRB or byte allocation")
            queue = queue_by_bearer[key]
            if allocation.scheduled_bytes > queue.queued_bytes + queue.retransmission_bytes:
                raise ValueError(f"Scheduler over-allocated bytes for bearer {key!r}")
            seen.add(key)
            allocated_prbs += allocation.prbs
        if allocated_prbs > request.total_prbs:
            raise ValueError(
                f"Scheduler allocated {allocated_prbs} PRBs but only {request.total_prbs} are available"
            )


# Compatibility for existing imports; new code should use MultiAgentRanScenario uniformly.
RanUploadScenario = MultiAgentRanScenario


def _mock_ue_ip(index: int) -> str:
    """Allocate non-conflicting private IPv4 addresses for the current mock."""

    third_octet = index // 240
    fourth_octet = 15 + index % 240
    if third_octet > 254:
        raise ValueError("Mock UE IPv4 pool exhausted")
    return f"10.20.{third_octet}.{fourth_octet}"


def rlc_queue_placeholder(ue_request: UERequest, drb: Drb) -> RlcQueue:
    """UL placeholder queue (0 bytes) for DL services: keeps ServiceContext structure consistent and does not compete for scheduling."""

    return RlcQueue(
        ue_id=drb.ue_id,
        drb_id=drb.drb_id,
        qfi=drb.qfi,
        slice_id=drb.slice_id,
        direction="UL",
        rlc_mode=drb.rlc_mode,
        queued_bytes=0,
        retransmission_bytes=0,
        head_of_line_delay_ms=0.0,
    )
class RanUploadScenario:
    """Project implementation detail."""

    def __init__(self, scene, scheduler=None) -> None:
        self.scene = scene
        self.scheduler = scheduler or JavaSchedulerAdapter()
        self.intent = AgentIntent(
            intent_id="intent_student_a_1",
            agent_id="student_a",
            agent_pos=Position(520.0, 430.0),
            action="upload",
            target="youtube_server",
            content_type="video",
            service_type="video_upload",
            requested_payload_bytes=100 * 1024 * 1024,
        )
        self.gnb = load_gnb_site_from_scene(scene)
        self.ue_state = build_demo_ue_state(
            agent_id=self.intent.agent_id,
            ue_id="student_a_phone",
            position=self.intent.agent_pos,
        )
        self.ue_state = register_ue(self.ue_state)
        self.ue_request = build_ue_request(
            self.intent,
            ue_id=self.ue_state.ue_id,
            service_instance_id=f"service_{self.intent.intent_id}",
            selected_access="5g",
        )
        self.access = select_access(self.ue_request, self.gnb)
        self.slice_id = classify_slice(self.ue_request.service_type)
        self.session = establish_pdu_session(self.ue_state, self.ue_request, slice_id=self.slice_id)
        self.traffic = build_ip_traffic(self.ue_request, self.session)
        self.qos_flow = build_qos_flow(self.ue_request, self.session)
        self.drb = map_qos_flow_to_drb(self.qos_flow, self.ue_request)
        self.pdcp = PdcpEntity(
            drb_id=self.drb.drb_id,
            qfi=self.drb.qfi,
            slice_id=self.drb.slice_id,
        )
        self.rlc = RlcEntity(
            ue_id=self.drb.ue_id,
            drb_id=self.drb.drb_id,
            qfi=self.drb.qfi,
            slice_id=self.drb.slice_id,
            direction=self.drb.direction,
            mode=self.drb.rlc_mode,
        )
        self.slice_policies = update_slice_policies()
        self.completed = False
        self.ticks_executed = 0
        self.cumulative_attempted_bytes = 0
        self.cumulative_successful_bytes = 0
        self.cumulative_failed_bytes = 0
        self.cumulative_dropped_bytes = 0
        self.cumulative_n3_loss_bytes = 0
        self.cumulative_n6_loss_bytes = 0
        self.last_state: dict[str, Any] | None = None

    def step(self, tick: int) -> dict[str, Any]:
        """Project implementation detail."""

        if self.completed:
            return self.snapshot(tick=tick, status="completed")

        # ① PDCP inflow — generate batch from traffic, enqueue into RLC
        batch = self.pdcp.process(self.traffic, tick=tick)
        self.rlc.enqueue(batch)

        # ② Report RLC queue state to MAC scheduler (simplified BSR)
        channel = estimate_channel(tick=tick, scene=self.scene, ue_request=self.ue_request, gnb=self.gnb)
        scheduler_request = build_scheduler_request(
            simulation_id="ran_upload_scenario",
            tick=tick,
            gnb_id=self.gnb.gnb_id,
            total_prbs=self.gnb.total_prbs,
            rlc_queues=[self.rlc.to_queue_state()],
            qos_flows=[self.qos_flow],
            drbs=[self.drb],
            channel_states=[channel],
            slice_policies=self.slice_policies,
        )

        # ③ MAC scheduling
        scheduler_result = self.scheduler.allocate(scheduler_request)
        if not scheduler_result.allocations:
            self.completed = True
            return self.snapshot(tick=tick, status="no_allocation")

        allocation = scheduler_result.allocations[0]
        if allocation.scheduled_bytes <= 0:
            self.completed = True
            return self.snapshot(tick=tick, status="zero_allocation")

        # ④ RLC segmentation/dequeue (grant phase)
        grant_result = self.rlc.on_grant(allocation)

        actual_allocation = replace(
            allocation,
            scheduled_bytes=grant_result.actual_sent_bytes,
        )

        # ⑤ PHY transmission
        transmission = transmit(
            tick=tick,
            allocation=actual_allocation,
            channel=channel,
        )

        # ⑥ RLC feedback (result phase)
        self.rlc.on_transmission_result(transmission)

        # downstream forwarding (unchanged)
        ru_result = receive_radio(transmission)
        n3 = build_n3_result(apply_backhaul(forward_to_n3(ru_result, self.session)))
        n6 = forward_n6(forward_via_upf(n3, self.session, target=self.ue_request.target))
        delivered = deliver_to_data_network(n6)

        # cumulative statistics (same accounting as before)
        self.ticks_executed += 1
        self.cumulative_attempted_bytes += transmission.attempted_bytes
        self.cumulative_successful_bytes += delivered.delivered_bytes
        self.cumulative_failed_bytes += transmission.failed_bytes + n3.n3_loss_bytes + delivered.n6_loss_bytes
        self.cumulative_dropped_bytes += transmission.dropped_bytes
        self.cumulative_n3_loss_bytes += n3.n3_loss_bytes
        self.cumulative_n6_loss_bytes += delivered.n6_loss_bytes

        # ⑦ completion check (traffic exhausted AND RLC queues empty AND no inflight)
        if (self.traffic.remaining_bytes <= 0
                and self.rlc.queued_bytes <= 0
                and self.rlc.retransmission_bytes <= 0
                and self.rlc.inflight_new_bytes <= 0
                and self.rlc.inflight_retx_bytes <= 0):
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
        rlc_state = self.rlc.to_queue_state()
        delivered_payload_bytes = min(self.traffic.total_bytes, self.cumulative_successful_bytes)
        dropped_bytes = (self.cumulative_dropped_bytes
                         + self.cumulative_n3_loss_bytes
                         + self.cumulative_n6_loss_bytes
                         + self.rlc.dropped_bytes)
        remaining_payload_bytes = max(0, self.traffic.total_bytes - delivered_payload_bytes - dropped_bytes)
        remaining_queue_bytes = rlc_state.queued_bytes + rlc_state.retransmission_bytes
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
            "drb": asdict(self.drb),
            "rlc_grant": asdict(grant_result),
            "rlc_queue_after": asdict(rlc_state),
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

    def snapshot(self, *, tick: int, status: str | None = None) -> dict[str, Any]:
        """Project implementation detail."""

        if self.last_state is not None:
            state = dict(self.last_state)
            state["tick"] = tick
            state["status"] = status or state.get("status", "running")
            return state
        rlc_state = self.rlc.to_queue_state()
        return {
            "mode": "tick",
            "status": status or "initialized",
            "tick": tick,
            "ticks_executed": self.ticks_executed,
            "gnb": asdict(self.gnb),
            "ue_request": asdict(self.ue_request),
            "access": asdict(self.access),
            "rlc_queue_after": asdict(rlc_state),
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
                "remaining_queue_bytes": rlc_state.queued_bytes + rlc_state.retransmission_bytes,
                "completion_ratio": 0.0,
                "remaining_ratio": 1.0,
                "dropped_bytes": self.cumulative_dropped_bytes + self.cumulative_n3_loss_bytes + self.cumulative_n6_loss_bytes,
            },
        }
