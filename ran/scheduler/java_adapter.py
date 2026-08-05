from __future__ import annotations

import json
from dataclasses import asdict

from ran.contracts import CONTRACT_VERSION, MacAllocation, SchedulerRequest, SchedulerResult
from .python_baseline import PythonBaselineScheduler


class JavaSchedulerAdapter:
    """Project implementation detail."""

    def __init__(self, fallback: PythonBaselineScheduler | None = None) -> None:
        self.fallback = fallback or PythonBaselineScheduler()

    def allocate(self, request: SchedulerRequest) -> SchedulerResult:
        """Project implementation detail."""

        payload = self.to_json(request)
        raw_result = self._send_to_java(payload)
        return self.from_json(raw_result)

    def to_json(self, request: SchedulerRequest) -> str:
        """Project implementation detail."""

        return json.dumps(asdict(request), ensure_ascii=False)

    def from_json(self, raw: str) -> SchedulerResult:
        """将 Java 或 fallback 返回的稳定 JSON 还原为 SchedulerResult。"""

        data = json.loads(raw)
        if data.get("contract_version") != CONTRACT_VERSION:
            raise ValueError(f"Unsupported scheduler contract version: {data.get('contract_version')!r}")
        allocations = [MacAllocation(**item) for item in data.get("allocations", [])]
        return SchedulerResult(
            contract_version=str(data["contract_version"]),
            simulation_id=str(data["simulation_id"]),
            scheduler_request_id=str(data["scheduler_request_id"]),
            tick=int(data["tick"]),
            allocations=allocations,
            debug=dict(data.get("debug", {})),
        )

    def _send_to_java(self, payload: str) -> str:
        """Project implementation detail."""

        request_data = json.loads(payload)
        request = _request_from_dict(request_data)
        result = self.fallback.allocate(request)
        return json.dumps(asdict(result), ensure_ascii=False)


def _request_from_dict(data: dict) -> SchedulerRequest:
    from ran.contracts import ChannelState, Drb, QoSFlow, RlcQueue, SlicePolicy

    return SchedulerRequest(
        contract_version=str(data["contract_version"]),
        simulation_id=str(data["simulation_id"]),
        scheduler_request_id=str(data["scheduler_request_id"]),
        tick=int(data["tick"]),
        gnb_id=str(data["gnb_id"]),
        direction=data["direction"],
        total_prbs=int(data["total_prbs"]),
        rlc_queues=[RlcQueue(**item) for item in data.get("rlc_queues", [])],
        qos_flows=[QoSFlow(**item) for item in data.get("qos_flows", [])],
        drbs=[Drb(**item) for item in data.get("drbs", [])],
        channel_states=[ChannelState(**item) for item in data.get("channel_states", [])],
        slice_policies=[SlicePolicy(**item) for item in data.get("slice_policies", [])],
        harq_feedback=list(data.get("harq_feedback", [])),
    )
