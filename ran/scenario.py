from __future__ import annotations

from dataclasses import asdict, replace
from typing import Any

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
)
from ran.core import Amf, Upf, deliver_to_data_network, establish_pdu_session, forward_via_upf, register_ue
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
from ran.traffic import build_ip_traffic
from ran.transport import apply_backhaul, build_n3_result, forward_n6
from ran.ue import build_demo_ue_state, build_ue_request


TERMINAL_SERVICE_STATUSES = {"COMPLETED", "FAILED"}


class MultiAgentRanScenario:
    """固定 Agent 集合的 RAN 场景编排器；协议细节由各模块继续完善。"""

    def __init__(
        self,
        scene,
        scheduler=None,
        *,
        definition: RanScenarioDefinition | None = None,
        agent_state_provider: AgentStateProvider | None = None,
        tick_ms: float = 1000.0,
        n3_bandwidth_mbps: float | None = None,
    ) -> None:
        
        self.scene = scene
        self.scheduler = scheduler or JavaSchedulerAdapter()
        self.tick_ms = float(tick_ms)
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
        self.ues: dict[str, UeContext] = {}
        self.services: dict[str, ServiceContext] = {}
        self.service_order: list[str] = []
        self.completed = False
        self.ticks_executed = 0
        self.last_state: dict[str, object] | None = None

        initial_states = self._read_agent_states(tick=0)
        self._build_contexts(initial_states)

    def _ensure_hybrid_ckm(self) -> None:
        """hybrid 信道模式:模拟启动时构建(或加载缓存)混合 CKM 并挂到 scene。

        构建失败/关闭时 scene.ckm 保持 None,estimate_channel 自动回退。
        环境变量 RAN_DISABLE_CKM=1 可跳过构建(测试环境用)。
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
                    f"[ckm] hybrid CKM 就绪: cells={len(ckm.cells)} "
                    f"refs={ckm.model_metadata.get('reference_count')} "
                    f"build={ckm.model_metadata.get('build_seconds')}s",
                    flush=True,
                )
        except Exception as exc:  # CKM 失败不阻塞模拟(回退 shadow)
            print(f"[ckm] 混合 CKM 构建失败,回退 shadow: {exc}", file=sys.stderr, flush=True)

    def step(self, tick: int) -> dict[str, object]:
        """推进一个 tick：汇总所有活跃队列，调度一次，再逐业务执行。"""

        if self.completed:
            # 无活跃业务时仍刷新 RAN 侧 Agent 副本,避免嵌套快照过期
            # (此前 completed 快速路径不重读 Agent 坐标,预览页读取该
            #  副本时移动阶段呈现冻结,直到首个意图提交场景重新激活)
            self._update_agent_states(tick)
            return self.snapshot(tick=tick, status="completed")

        self._update_agent_states(tick)
        active_services = [
            self.services[service_id]
            for service_id in self.service_order
            if self.services[service_id].status not in TERMINAL_SERVICE_STATUSES
        ]
        if not active_services:
            self.completed = True
            return self.snapshot(tick=tick, status="completed")

        # N3 流转:UPF 缓冲 → gNB DL 队列(下行;默认瞬时到达,受 n3 带宽约束)。
        # 放在调度之前,保证本次调度窗口能看到已到达 gNB 的下行数据。
        for service in active_services:
            if service.dl_queue is not None:
                dl_tunnel = self.upf.tunnel_of(service.session.pdu_session_id, "DL")
                if dl_tunnel is not None:
                    n3_tx = self.upf.forward_to_gnb(dl_tunnel, tick_ms=self.tick_ms)
                    if n3_tx > 0:
                        if service.rlc is not None:
                            service.rlc.enqueue_bytes(n3_tx)
                        else:
                            service.dl_queue.queued_bytes += n3_tx
                    service.upf_buffered_bytes = self.upf.buffered_bytes(service.session.pdu_session_id)
                    service.n3_gtp_overhead_bytes = dl_tunnel.overhead_total_bytes

        # UL inflow:实体管道 PDCP→RLC 入队(调度前,本 tick 新数据可见)
        for service in active_services:
            if service.rlc is not None and service.dl_queue is None:
                service.rlc.enqueue(service.pdcp.process(service.traffic, tick=tick))

        channel_by_service = {}
        channel_by_link = {}
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
            rlc_queues=[self._rlc_queue_state(service) for service in active_services]
            + [service.dl_queue for service in active_services if service.dl_queue is not None and service.rlc is None],
            qos_flows=[service.qos_flow for service in active_services],
            drbs=[service.drb for service in active_services],
            channel_states=list(channel_by_link.values()),
            slice_policies=self.slice_policies,
            slot_ms=self.tick_ms,
        )
        scheduler_result = self.scheduler.allocate(scheduler_request)
        self._validate_scheduler_result(scheduler_request, scheduler_result)
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
                service.status = "WAITING_FOR_ALLOCATION"
                service_states.append(self._build_waiting_service_state(service, channel, tick))
                continue

            # 最小 RLC grant mock:当前仅按队列字节截断;后续替换为真实 segment 列表。
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

        self.ticks_executed += 1
        self._refresh_lifecycle_states(tick)
        self.completed = all(
            service.status in TERMINAL_SERVICE_STATUSES for service in self.services.values()
        )
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

    # ------------------------------------------------------------- 实体管道辅助(xizhe)

    def _rlc_queue_state(self, service) -> RlcQueue:
        """实体管道:返回 RLC 实体队列状态;函数式兼容返回原队列。"""

        rlc = getattr(service, "rlc", None)
        if rlc is not None:
            return rlc.to_queue_state()
        if service.dl_queue is not None:
            return service.dl_queue
        return service.rlc_queue

    def _queue_drained(self, service) -> bool:
        """队列耗尽判定(实体含 inflight;函数式含 queued/retransmission)。"""

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
        """实体管道单 tick:on_grant 分段 → PHY 传输 → on_transmission_result 反馈。"""

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
        """公开 mock/真实 AgentStateProvider 的统一状态接口。"""

        states = self._read_agent_states(tick)
        return [asdict(state) for state in states]

    def snapshot(self, *, tick: int, status: str | None = None) -> dict[str, object]:
        """返回当前场景快照，不推进协议状态。"""

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
        state_by_agent = {state.agent_id: state for state in initial_states}
        for index, item in enumerate(self.definition.agents):
            agent_state = state_by_agent[item.agent_id]
            self._register_ue(item, agent_state)
            if item.intent is None:
                # 无初始 Intent:仅注册 UE,业务由运行时通过 submit_intent 动态提交。
                self.agents[item.agent_id] = AgentContext(
                    agent_id=item.agent_id,
                    state=agent_state,
                    intent_ids=[],
                    ue_ids=[item.ue_id],
                )
                continue
            self._create_service(item, item.intent, index)

    def _register_ue(self, item, agent_state) -> None:
        """注册并保存 Agent 的 UE 控制面上下文。重复注册同一 UE 时保持现有上下文。"""

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
        """根据一个 Intent 构建完整业务上下文,返回 service_instance_id。"""

        service_instance_id = f"service_{intent.intent_id}"
        ue_state = self.ues[item.ue_id].state
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
        traffic = build_ip_traffic(ue_request, session)
        qos_flow = build_qos_flow(ue_request, session)
        drb = map_qos_flow_to_drb(qos_flow, ue_request)
        # 函数式批仅作口径/统计;实体管道从原 traffic 每 tick 消费。
        # 用副本构建批,避免消耗 traffic.remaining_bytes 导致 UL 实体
        # inflow 无数据(实体切换遗留:UL 队列恒空、永不获调度)。
        pdcp_batch = build_pdcp_batch(replace(traffic), drb)
        is_downlink = ue_request.direction == "DL"
        # xizhe 实体管道(PDCP/RLC 实体;函数式 build_* 保留为兼容口径)
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
        # GTP-U 隧道(UL/DL 都建立;UL 用于 N3 交付统计,DL 用于缓冲-转发)
        tunnel = self.upf.create_tunnel(session.pdu_session_id, ue_request.direction)
        if is_downlink:
            # 下行:DN 数据经 N6 到达 UPF 缓冲(UE 挂起期间不丢);
            # 每 tick 由 N3 流转填充 gNB 侧 RLC 队列(实体 enqueue_bytes)。
            # 注意:缓冲与队列使用同一口径(pdcp_batch.output_bytes),
            # 初始队列清空(数据全部在 UPF 缓冲),避免双倍入队。
            self.upf.receive_from_dn(session.pdu_session_id, pdcp_batch.output_bytes)
            dl_queue = replace(build_rlc_queue(pdcp_batch, drb), queued_bytes=0, retransmission_bytes=0)
            rlc_queue = replace(rlc_queue_placeholder(ue_request, drb))
        else:
            dl_queue = None
            rlc_queue = build_rlc_queue(pdcp_batch, drb)

        # RRC 建立:业务需要无线承载 → IDLE/INACTIVE → CONNECTED。
        self.amf.establish_rrc(ue_state)

        agent_context = self.agents.get(item.agent_id)
        if agent_context is None:
            # 理论不可达:_build_contexts 总会先注册 AgentContext;此处兜底保证不变量。
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
            upf_buffered_bytes=self.upf.buffered_bytes(session.pdu_session_id),
            n3_tunnel_id=tunnel.tunnel_id,
            status="ACTIVE",
        )
        self.service_order.append(service_instance_id)
        return service_instance_id

    def submit_intent(self, intent: AgentIntent, *, selected_access: str = "5g") -> str:
        """运行中提交一个新的业务意图,返回 service_instance_id。

        校验:
        - agent_id 必须属于场景建立时冻结的 Agent 集合。
        - intent_id 必须全局唯一。
        - requested_payload_bytes 必须为正。
        提交后若场景此前已 completed,会重新激活 step 循环。
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
        """为动态提交的业务分配稳定且唯一的 UE IPv4 索引。"""

        index = getattr(self, "_service_index_counter", len(self.service_order))
        self._service_index_counter = index + 1
        return index

    def _execute_service_tick(self, service, channel, allocation, tick: int) -> dict[str, object]:
        service.status = "ACTIVE"
        if service.dl_queue is not None:
            return self._execute_downlink_tick(service, channel, allocation, tick)
        if service.rlc is not None:
            # xizhe 实体管道:on_grant 分段 → PHY → on_transmission_result
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
        # 上行经 UPF 实体(N3 到达 → N6 交付 DN;带 GTP-U 隧道开销统计)
        n6 = forward_n6(self.upf.forward_to_dn(n3, service.session, target=service.ue_request.target))
        ul_tunnel = self.upf.tunnel_of(service.session.pdu_session_id, "UL")
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
        """下行 tick:DN 侧数据经 gNB 无线链路交付到 UE。

        与上行对称:传输成功字节 = UE 接收字节;完成 = DL 队列清空。
        N3/N6 为零值占位(数据由 DN 直达 gNB,不经 UE 上行转发)。
        """

        if service.rlc is not None:
            # xizhe 实体管道:on_grant 分段 → PHY → on_transmission_result
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
            and self.upf.buffered_bytes(service.session.pdu_session_id) <= 0
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
        """该 UE 无活跃业务时挂起 RRC:CONNECTED→INACTIVE(3GPP 业务间隙行为)。"""

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
            "upf_buffered_bytes": service.upf_buffered_bytes,
            "n3_tunnel_id": service.n3_tunnel_id,
            "n3_gtp_overhead_bytes": service.n3_gtp_overhead_bytes,
            "ue_request": asdict(service.ue_request),
            "access": asdict(service.access),
            "qos_flow": asdict(service.qos_flow),
            "drb": asdict(service.drb),
        }

    def _agent_state_with_cp(self, agent_id: str) -> dict[str, object]:
        """Agent 快照 + 该 Agent UE 的 CM/RRC 控制面状态(前端展示)。"""

        snapshot = asdict(self.agents[agent_id].state)
        for ue_context in self.ues.values():
            if ue_context.state.agent_id == agent_id:
                snapshot["cm_state"] = ue_context.state.cm_state
                snapshot["rrc_state"] = ue_context.state.rrc_state
                break
        return snapshot

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
            "progress": progress,
            # 兼容旧预览：只映射首个 Service，后续前端应读取 service_states。
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
        """按原始 PDCP batch 比例映射协议结果，防止 header 被计为应用 payload。"""

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
                # 无任何已提交 Intent(动态模式):不派生生命周期状态,保留 provider 状态。
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


# 兼容已有导入；新代码统一使用 MultiAgentRanScenario。
RanUploadScenario = MultiAgentRanScenario


def _mock_ue_ip(index: int) -> str:
    """为当前 mock 分配互不冲突的私网 IPv4 地址。"""

    third_octet = index // 240
    fourth_octet = 15 + index % 240
    if third_octet > 254:
        raise ValueError("Mock UE IPv4 pool exhausted")
    return f"10.20.{third_octet}.{fourth_octet}"


def rlc_queue_placeholder(ue_request: UERequest, drb: Drb) -> RlcQueue:
    """DL 业务的 UL 占位队列(0 字节):保持 ServiceContext 结构一致,不参与调度竞争。"""

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
