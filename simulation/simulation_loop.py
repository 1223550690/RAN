from __future__ import annotations

import time

from .clock import SimulationClock
from .state import SimulationState


class SimulationLoop:
    def __init__(
        self,
        state: SimulationState,
        *,
        clock: SimulationClock,
        preview_service=None,
        ran_scenario=None,
        control=None,
        orchestrator=None,
    ) -> None:
        self.state = state
        self.clock = clock
        self.preview_service = preview_service
        self.ran_scenario = ran_scenario
        self.control = control
        self.orchestrator = orchestrator
        self.ran_state: dict | None = None
        self.agent_frame = None
        self.console: list[str] = []

    def run(self, total_ticks: int) -> None:
        self.log("simulation started")
        self.write_preview_state(now_seconds=0.0)
        for _ in range(total_ticks):
            self.wait_if_paused()
            self.state.tick = self.clock.step()
            now_seconds = self.state.tick * self.clock.tick_ms / 1000
            if self.orchestrator is not None:
                self.agent_frame = self.orchestrator.step(self.state.tick)
                self.ran_state = self.orchestrator.ran_state
            elif self.ran_scenario is not None:
                self.ran_state = self.ran_scenario.step(self.state.tick)
            line = self.format_tick()
            self.log(line)
            self.write_preview_state(now_seconds=now_seconds)
            print(line, flush=True)
            time.sleep(self.clock.tick_ms / 1000)

    def write_preview_state(self, *, now_seconds: float) -> None:
        if self.preview_service is not None:
            self.preview_service.write_state(
                tick=self.state.tick,
                now_seconds=now_seconds,
                scene=self.state.scene,
                agents=list(self.agent_frame.agents) if self.agent_frame is not None else [],
                ran_requests=[],
                ran_state=self.ran_state,
                control_state=self.control.snapshot() if self.control is not None else {},
                console=self.console,
            )

    def format_tick(self) -> str:
        lines: list[str] = []
        if self.agent_frame is not None:
            lines.append(self.format_agent_frame_lines(self.agent_frame))
        if self.ran_state:
            lines.extend(self.format_ran_state_lines(self.ran_state))
        if not lines:
            return f"tick={self.state.tick} | agent_input=disabled"
        return " | ".join(lines)

    def format_agent_frame_lines(self, frame) -> str:
        """输出每个 Agent 的简要状态:状态 / 活动 / 位置 / 目标。"""

        parts = []
        for agent in frame.agents:
            position = agent.position
            parts.append(
                f"{agent.agent_id}={agent.activity_state}"
                f"({position[0]:.2f},{position[1]:.2f})"
                f"{'->' + agent.destination_id if agent.destination_id else ''}"
            )
        return "agents[" + ", ".join(parts) + "]"

    def format_ran_state_lines(self, ran_state: dict) -> list[str]:
        service_states = ran_state.get("service_states")
        if isinstance(service_states, list) and service_states:
            return self.format_multi_agent_state_lines(ran_state, service_states)

        result = ran_state.get("result", {})
        qos = result.get("qos", {}) if isinstance(result, dict) else {}
        progress = ran_state.get("progress", {})
        channel = ran_state.get("channel", {})
        scheduler_result = ran_state.get("scheduler_result", {})
        allocations = scheduler_result.get("allocations", []) if isinstance(scheduler_result, dict) else []
        allocation = allocations[0] if allocations else {}
        transmission = ran_state.get("transmission", {})
        gnb = ran_state.get("gnb", {})
        position = gnb.get("position", {}) if isinstance(gnb, dict) else {}
        ue_request = ran_state.get("ue_request", {})
        drb = ran_state.get("drb", {})
        qos_flow = ran_state.get("qos_flow", {})

        status_line = (
            f"ran {ran_state.get('status', '-')}"
            f" tick={ran_state.get('tick', self.state.tick)}"
            f" ue={ue_request.get('ue_id', '-')}"
            f" gnb={gnb.get('gnb_id', '-')}"
            f" pos=({self.format_number(position.get('x'))}, {self.format_number(position.get('y'))})"
            f" slice={result.get('slice_id', '-')}"
            f" qfi={qos_flow.get('qfi', '-')}"
            f" drb={drb.get('drb_id', '-')}"
            f" cqi={channel.get('cqi', '-')}"
            f" sinr={self.format_float(channel.get('sinr_db'))}dB"
            f" prbs={allocation.get('prbs', transmission.get('prbs', '-'))}"
            f" mcs={allocation.get('mcs', transmission.get('mcs', '-'))}"
        )
        traffic_line = (
            f"ran tx={transmission.get('successful_bytes', '-')}"
            f" fail={transmission.get('failed_bytes', '-')}"
            f" total={progress.get('delivered_bytes', result.get('delivered_bytes', '-'))}"
            f" / {progress.get('requested_bytes', result.get('requested_bytes', '-'))}"
            f" remaining_payload={progress.get('remaining_payload_bytes', '-')}"
            f" queue_bytes={progress.get('remaining_queue_bytes', '-')}"
            f" completion_ratio={self.format_percent(progress.get('completion_ratio'))}"
            f" remaining_ratio={self.format_percent(progress.get('remaining_ratio'))}"
            f" tick_throughput_mbps={self.format_float(qos.get('throughput_mbps'))}"
            f" loss_rate={self.format_percent(qos.get('packet_loss_rate'))}"
            f" dropped={progress.get('dropped_bytes', '-')}"
        )
        return [status_line, traffic_line]

    def format_multi_agent_state_lines(self, ran_state: dict, service_states: list[dict]) -> list[str]:
        """为每个业务输出完整单 tick 行，并追加一行全局聚合信息。"""

        gnb = ran_state.get("gnb", {})
        position = gnb.get("position", {}) if isinstance(gnb, dict) else {}
        lines: list[str] = []
        for service in service_states:
            result = service.get("result", {})
            qos = result.get("qos", {}) if isinstance(result, dict) else {}
            progress = service.get("progress", {})
            channel = service.get("channel", {})
            allocation = service.get("allocation", {})
            transmission = service.get("transmission", {})
            qos_flow = service.get("qos_flow", {})
            drb = service.get("drb", {})
            lines.append(
                f"ran agent={service.get('agent_id', '-')}"
                f" service={service.get('service_instance_id', '-')}"
                f" status={service.get('status', '-')}"
                f" tick={service.get('tick', ran_state.get('tick', self.state.tick))}"
                f" ue={service.get('ue_id', '-')}"
                f" gnb={gnb.get('gnb_id', '-')}"
                f" gnb_pos=({self.format_number(position.get('x'))}, {self.format_number(position.get('y'))})"
                f" slice={result.get('slice_id', '-')}"
                f" qfi={qos_flow.get('qfi', '-')}"
                f" drb={drb.get('drb_id', '-')}"
                f" cqi={channel.get('cqi', '-')}"
                f" sinr={self.format_float(channel.get('sinr_db'))}dB"
                f" prbs={allocation.get('prbs', '-')}"
                f" mcs={allocation.get('mcs', '-')}"
                f" layers={allocation.get('layers', '-')}"
                f" tx={transmission.get('successful_bytes', 0)}"
                f" fail={transmission.get('failed_bytes', 0)}"
                f" delivered={progress.get('delivered_bytes', 0)}"
                f" / {progress.get('requested_bytes', '-')}"
                f" remaining_payload={progress.get('remaining_payload_bytes', '-')}"
                f" queue_bytes={progress.get('remaining_queue_bytes', '-')}"
                f" completion_ratio={self.format_percent(progress.get('completion_ratio'))}"
                f" remaining_ratio={self.format_percent(progress.get('remaining_ratio'))}"
                f" tick_throughput_mbps={self.format_float(qos.get('throughput_mbps'))}"
                f" loss_rate={self.format_percent(qos.get('packet_loss_rate'))}"
                f" dropped={progress.get('dropped_bytes', 0)}"
            )

        progress = ran_state.get("progress", {})
        lines.append(
            f"ran total agents={ran_state.get('agent_count', len(service_states))}"
            f" status={ran_state.get('status', '-')}"
            f" tick={ran_state.get('tick', self.state.tick)}"
            f" delivered={progress.get('delivered_bytes', 0)}"
            f" / {progress.get('requested_bytes', '-')}"
            f" remaining_payload={progress.get('remaining_payload_bytes', '-')}"
            f" queue_bytes={progress.get('remaining_queue_bytes', '-')}"
            f" completion_ratio={self.format_percent(progress.get('completion_ratio'))}"
            f" remaining_ratio={self.format_percent(progress.get('remaining_ratio'))}"
            f" dropped={progress.get('dropped_bytes', 0)}"
        )
        return lines

    @staticmethod
    def format_float(value) -> str:
        return f"{value:.3f}" if isinstance(value, (int, float)) else "-"

    @staticmethod
    def format_number(value) -> str:
        if not isinstance(value, (int, float)):
            return "-"
        return str(int(value)) if float(value).is_integer() else f"{value:.1f}"

    @staticmethod
    def format_percent(value) -> str:
        return f"{value * 100:.2f}%" if isinstance(value, (int, float)) else "-"

    def log(self, message: str) -> None:
        self.console.append(message)
        if self.control is not None:
            self.control.append_log(message)
        if len(self.console) > 120:
            del self.console[:-120]

    def wait_if_paused(self) -> None:
        if self.control is None:
            return
        while self.control.paused:
            self.write_preview_state(now_seconds=self.state.tick * self.clock.tick_ms / 1000)
            time.sleep(0.1)
