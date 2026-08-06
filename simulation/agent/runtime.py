"""AgentRuntime:单个 Agent 的状态推进(规划 → 移动 → 提交意图 → 等待业务)。

约束:
- 只在 PLANNING 时调用计划提供者(仿真开始或收到业务完成事件后)。
- WALKING 中不产生任何网络流量;NETWORK_ACTIVE 中坐标保持不变。
- 每个 Agent 同时最多一个活跃意图。
"""

from __future__ import annotations

from .contracts import AgentPlan, AgentSnapshot, AgentSpawnDefinition
from .navigation import NavigationPlanner
from .planning import AgentPlanProvider, validate_plan
from .adapters.ran_intent_gateway import RanIntentGateway
from .state_machine import AgentStateMachine

MAX_PLAN_RETRIES = 1  # 计划校验/导航失败后的重试次数。


class AgentRuntime:
    def __init__(
        self,
        definition: AgentSpawnDefinition,
        *,
        plan_provider: AgentPlanProvider,
        navigation: NavigationPlanner,
        gateway: RanIntentGateway | None = None,
        speed_m_per_tick: float = 0.5,
        same_building_only: bool = False,
    ) -> None:
        self.definition = definition
        self.plan_provider = plan_provider
        self.navigation = navigation
        self.gateway = gateway
        self.speed_m_per_tick = max(0.01, speed_m_per_tick)
        self.same_building_only = same_building_only
        self.state_machine = AgentStateMachine()
        self.position: tuple[float, float] = definition.spawn_position
        self.current_plan: AgentPlan | None = None
        self.waypoints: list[tuple[float, float]] = []
        self.waypoint_index: int = 0
        self.destination_id: str | None = None
        self.current_intent_id: str | None = None
        self.active_service_id: str | None = None
        self.error: str | None = None
        self.completed_intents: list[dict] = []
        self._plan_retries = 0

    # ------------------------------------------------------------------ tick 推进

    def step(self, tick: int) -> None:
        state = self.state_machine.state
        if state == "READY":
            self._enter_planning(tick)
        elif state == "PLANNING":
            self._do_planning(tick)
        elif state == "WALKING":
            self._do_walking(tick)
        elif state == "NETWORK_PENDING":
            self._do_submit(tick)
        # NETWORK_ACTIVE / DONE / FAILED:等待外部事件,不做任何推进。

    # ------------------------------------------------------------------ 状态动作

    def _enter_planning(self, tick: int) -> None:
        self.error = None
        self.state_machine.transition("start_planning", tick)

    def _do_planning(self, tick: int) -> None:
        catalog = list(self.navigation.semantic_index.by_name.keys())
        current_building = None
        if self.same_building_only:
            current_building = self._current_building_id()
            if current_building is not None:
                building = self.navigation.semantic_index.get_area(current_building)
                prefix = building.path.lower()  # catalog 的 key 均为小写。
                filtered = [
                    name
                    for name in catalog
                    if name == prefix or name.startswith(prefix + " / ")
                ]
                # 排除当前所在区域(含建筑本体),保证 LLM 必须选择同建筑内其他区域。
                current_room = self.current_room()
                exclude: set[str] = set()
                if current_room:
                    room = self.navigation.semantic_index.get_area(current_room)
                    if room is not None:
                        exclude.add(room.path.lower())
                        exclude.add(room.area_id.lower())
                remaining = [name for name in filtered if name not in exclude]
                if remaining:  # 排除后为空时回退全建筑 catalog。
                    catalog = remaining
                else:
                    catalog = filtered
        context = {
            "tick": tick,
            "role": self.definition.role,
            "current_building": current_building,
            "current_location": self.current_room() or "outside",
            "completed_intents": self.completed_intents,
            "destination_catalog": catalog,
        }
        plan = self.plan_provider.request_plan(self.definition.agent_id, context)
        if plan is None:
            self.state_machine.transition("no_more_plans", tick)
            return

        valid, error = validate_plan(plan, self.navigation)
        if not valid:
            self._handle_plan_failure(error or "invalid plan", tick)
            return

        self.current_plan = plan
        self._plan_retries = 0

        if plan.stay:
            # 不动移动模板:就地在 spawn 位置提交意图,直接跳过 WALKING。
            self.waypoints = []
            self.waypoint_index = 0
            self.destination_id = plan.destination_ref or "stay_at_spawn"
            self.state_machine.transition("plan_ready", tick)
            self.state_machine.transition("arrived", tick)
            return

        result = self.navigation.plan_path(self.position, plan.destination_ref)
        if not result.ok:
            self._handle_plan_failure(result.error or "navigation failed", tick)
            return

        self.waypoints = list(result.plan.waypoints)
        self.waypoint_index = 0
        self.destination_id = plan.destination_ref
        self.state_machine.transition("plan_ready", tick)

    def _handle_plan_failure(self, error: str, tick: int) -> None:
        if self._plan_retries < MAX_PLAN_RETRIES:
            self._plan_retries += 1
            self.error = error
            # 重试:重新进入 PLANNING 请求新计划。
            return
        self.error = error
        self.state_machine.transition("plan_failed", tick)

    def _do_walking(self, tick: int) -> None:
        if not self.waypoints:
            self.state_machine.transition("arrived", tick)
            return
        remaining = self.speed_m_per_tick
        while remaining > 0 and self.waypoint_index < len(self.waypoints) - 1:
            target = self.waypoints[self.waypoint_index + 1]
            dx = target[0] - self.position[0]
            dy = target[1] - self.position[1]
            step_distance = (dx * dx + dy * dy) ** 0.5
            if step_distance <= remaining:
                self.position = target
                self.waypoint_index += 1
                remaining -= step_distance
            else:
                ratio = remaining / step_distance if step_distance > 0 else 0.0
                self.position = (
                    self.position[0] + dx * ratio,
                    self.position[1] + dy * ratio,
                )
                remaining = 0.0
        if self.waypoint_index >= len(self.waypoints) - 1:
            self.state_machine.transition("arrived", tick)

    def _do_submit(self, tick: int) -> None:
        if self.current_plan is None:
            self.error = "submit without a plan"
            self.state_machine.transition("plan_failed", tick)
            return
        if self.gateway is None:
            self.error = "intent gateway not attached"
            self.state_machine.transition("plan_failed", tick)
            return
        try:
            service_id = self.gateway.submit(
                agent_id=self.definition.agent_id,
                plan=self.current_plan,
                position=self.position,
                tick=tick,
                ue_id=self.definition.ue_id or f"{self.definition.agent_id}_phone",
            )
        except Exception as exc:  # noqa: BLE001 - 提交失败记录到状态帧。
            self.error = f"intent submit failed: {exc}"
            self.state_machine.transition("plan_failed", tick)
            return
        self.current_intent_id = _intent_id_of(service_id)
        self.active_service_id = service_id
        self.state_machine.transition("intent_submitted", tick)

    # ------------------------------------------------------------------ 外部事件

    def on_intent_terminal(self, intent_id: str, succeeded: bool, tick: int) -> None:
        """RAN 业务终态回调:仅在 NETWORK_ACTIVE 且意图匹配时响应。"""

        if self.state_machine.state != "NETWORK_ACTIVE":
            return
        if intent_id != self.current_intent_id:
            return
        if succeeded:
            self.completed_intents.append(
                {
                    "intent_id": intent_id,
                    "destination_ref": self.destination_id,
                    "intent_type": self.current_plan.intent_type if self.current_plan else "",
                    "completed_tick": tick,
                }
            )
            self.state_machine.transition("intent_completed", tick)
        else:
            self.error = f"intent failed: {intent_id}"
            self.state_machine.transition("intent_failed", tick)
        self.current_intent_id = None
        self.active_service_id = None

    def _current_building_id(self) -> str | None:
        """当前所在建筑(最顶层区域)ID;户外为 None。"""

        area = self.navigation.semantic_index.find_area_at(self.position)
        while area is not None and area.parent_id is not None:
            parent = self.navigation.semantic_index.get_area(area.parent_id)
            if parent is None:
                break
            area = parent
        return area.area_id if area is not None else None

    def current_room(self) -> str | None:
        return self.navigation.current_room(self.position)

    # ------------------------------------------------------------------ 快照

    def to_snapshot(self, tick: int) -> AgentSnapshot:
        machine = self.state_machine
        waypoint_count = len(self.waypoints)
        return AgentSnapshot(
            agent_id=self.definition.agent_id,
            role=self.definition.role,
            lifecycle_status=machine.lifecycle_status,
            activity_state=machine.activity_state,
            position=self.position,
            current_room_id=self.current_room(),
            destination_id=self.destination_id,
            current_intent_id=self.current_intent_id,
            waypoint_index=min(self.waypoint_index, max(0, waypoint_count - 1)),
            waypoint_count=waypoint_count,
            last_transition_tick=machine.last_transition_tick,
            error=self.error,
            waypoints=list(self.waypoints),
        )


def _intent_id_of(service_instance_id: str) -> str:
    """从 service_instance_id 反推 intent_id:service_{intent_id}。"""

    if service_instance_id.startswith("service_"):
        return service_instance_id[len("service_") :]
    return service_instance_id
