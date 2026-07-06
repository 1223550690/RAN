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
    ) -> None:
        self.state = state
        self.clock = clock
        self.preview_service = preview_service
        self.ran_scenario = ran_scenario
        self.control = control
        self.ran_state: dict | None = None
        self.console: list[str] = []

    def run(self, total_ticks: int) -> None:
        self.log("simulation started")
        self.write_preview_state(now_seconds=0.0)
        for _ in range(total_ticks):
            self.wait_if_paused()
            self.state.tick = self.clock.step()
            now_seconds = self.state.tick * self.clock.tick_ms / 1000
            if self.ran_scenario is not None:
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
                agents=[],
                ran_requests=[],
                ran_state=self.ran_state,
                control_state=self.control.snapshot() if self.control is not None else {},
                console=self.console,
            )

    def format_tick(self) -> str:
        if self.ran_state:
            return " | ".join(self.format_ran_state_lines(self.ran_state))
        return f"tick={self.state.tick} | agent_input=disabled"

    def format_ran_state_lines(self, ran_state: dict) -> list[str]:
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
            f" remaining={progress.get('remaining_queue_bytes', '-')}"
            f" completion_ratio={self.format_percent(progress.get('completion_ratio'))}"
            f" remaining_ratio={self.format_percent(progress.get('remaining_ratio'))}"
            f" tick_throughput_mbps={self.format_float(qos.get('throughput_mbps'))}"
            f" loss_rate={self.format_percent(qos.get('packet_loss_rate'))}"
            f" dropped={progress.get('dropped_bytes', '-')}"
        )
        return [status_line, traffic_line]

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
