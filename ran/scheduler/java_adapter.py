from __future__ import annotations

import json
from dataclasses import asdict

from ran.contracts import MacAllocation, SchedulerRequest, SchedulerResult
from .python_baseline import PythonBaselineScheduler


class JavaSchedulerAdapter:
    """Java scheduler 适配器。

    当前 MVP 暂时接到 PythonBaselineScheduler，保留完整 JSON 输入输出边界。
    后续接 Java 时，只需要替换 `_send_to_java`。
    """

    def __init__(self, fallback: PythonBaselineScheduler | None = None) -> None:
        self.fallback = fallback or PythonBaselineScheduler()

    def allocate(self, request: SchedulerRequest) -> SchedulerResult:
        """执行调度。

        输入:
        - SchedulerRequest: Python dataclass。

        输出:
        - SchedulerResult: Java 或 fallback 返回的分配结果。
        """

        payload = self.to_json(request)
        # MVP 最小实现：暂不启动 Java 常驻服务；把 JSON 交给 Python fallback 模拟 Java 返回。
        raw_result = self._send_to_java(payload)
        return self.from_json(raw_result)

    def to_json(self, request: SchedulerRequest) -> str:
        """把 SchedulerRequest 转成 Java 可读取 JSON。"""

        return json.dumps(asdict(request), ensure_ascii=False)

    def from_json(self, raw: str) -> SchedulerResult:
        """把 Java 返回 JSON 转回 SchedulerResult。"""

        data = json.loads(raw)
        allocations = [MacAllocation(**item) for item in data.get("allocations", [])]
        return SchedulerResult(tick=int(data["tick"]), allocations=allocations, debug=dict(data.get("debug", {})))

    def _send_to_java(self, payload: str) -> str:
        """预留 Java 进程/Socket/gRPC 调用点。"""

        request_data = json.loads(payload)
        request = _request_from_dict(request_data)
        result = self.fallback.allocate(request)
        return json.dumps(asdict(result), ensure_ascii=False)


def _request_from_dict(data: dict) -> SchedulerRequest:
    from ran.contracts import ChannelState, Drb, QoSFlow, RlcQueue, SlicePolicy

    return SchedulerRequest(
        tick=int(data["tick"]),
        direction=data["direction"],
        total_prbs=int(data["total_prbs"]),
        rlc_queues=[RlcQueue(**item) for item in data.get("rlc_queues", [])],
        qos_flows=[QoSFlow(**item) for item in data.get("qos_flows", [])],
        drbs=[Drb(**item) for item in data.get("drbs", [])],
        channel_states=[ChannelState(**item) for item in data.get("channel_states", [])],
        slice_policies=[SlicePolicy(**item) for item in data.get("slice_policies", [])],
        harq_feedback=list(data.get("harq_feedback", [])),
    )
