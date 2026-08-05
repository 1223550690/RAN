from __future__ import annotations

import math

from ran.contracts import (
    ChannelState,
    MacAllocation,
    RlcQueue,
    SchedulerRequest,
    SchedulerResult,
)
from ran.radio.ofdm import estimate_transport_bytes


class PythonBaselineScheduler:
    """Project implementation detail."""

    def allocate(self, request: SchedulerRequest) -> SchedulerResult:
        """Project implementation detail."""

        active = [queue for queue in request.rlc_queues if queue.queued_bytes + queue.retransmission_bytes > 0]
        if not active:
            return _build_result(request, allocations=[], debug={"reason": "no_active_queue"})

        channel_by_ue = {state.ue_id: state for state in request.channel_states}
        policy_by_slice = {policy.slice_id: policy for policy in request.slice_policies}
        weights: dict[tuple[str, int], float] = {}
        for queue in active:
            channel = channel_by_ue.get(queue.ue_id)
            policy = policy_by_slice.get(queue.slice_id)
            cqi = channel.cqi if channel else 1
            priority = policy.priority if policy else 5
            weight = max(1.0, (queue.queued_bytes + queue.retransmission_bytes) / 1_000_000) * max(1, cqi) / max(1, priority)
            weights[(queue.ue_id, queue.drb_id)] = weight

        prbs_by_queue = _apportion_prbs(weights, request.total_prbs)
        allocations: list[MacAllocation] = []
        for queue in active:
            channel = channel_by_ue.get(queue.ue_id)
            queue_key = (queue.ue_id, queue.drb_id)
            prbs = prbs_by_queue.get(queue_key, 0)
            if prbs <= 0:
                continue
            cqi = channel.cqi if channel else 1
            mcs = max(1, min(28, int(cqi * 1.8))) #Change how mcs works fundamentally
            layers = 1 if cqi < 10 else 2
            capacity = estimate_transport_bytes(prbs=prbs, mcs=mcs, layers=layers)
            scheduled = min(queue.queued_bytes + queue.retransmission_bytes, capacity)
            allocations.append(
                MacAllocation(
                    allocation_id=f"allocation_{request.simulation_id}_{request.tick}_{queue.ue_id}_{queue.drb_id}",
                    ue_id=queue.ue_id,
                    drb_id=queue.drb_id,
                    qfi=queue.qfi,
                    slice_id=queue.slice_id,
                    direction=queue.direction,
                    prbs=prbs,
                    mcs=mcs,
                    layers=layers,
                    scheduled_bytes=scheduled, 
                    expected_error_rate=channel.estimated_packet_error_rate if channel else 0.2,
                    is_retransmission=queue.retransmission_bytes > 0,
                )
            )
        return _build_result(request, allocations=allocations, debug={"implementation": "python_baseline"})


def _apportion_prbs(weights: dict[tuple[str, int], float], total_prbs: int) -> dict[tuple[str, int], int]:
    """使用最大余数法进行整数分配，保证 PRB 总量严格守恒。"""

    if total_prbs <= 0 or not weights:
        return {key: 0 for key in weights}
    weight_sum = sum(max(0.0, weight) for weight in weights.values())
    if weight_sum <= 0.0:
        return {key: 0 for key in weights}

    raw = {key: total_prbs * max(0.0, weight) / weight_sum for key, weight in weights.items()}
    apportioned = {key: math.floor(value) for key, value in raw.items()}
    remainder = total_prbs - sum(apportioned.values())
    ranked = sorted(raw, key=lambda key: (-(raw[key] - apportioned[key]), key))
    for key in ranked[:remainder]:
        apportioned[key] += 1
    return apportioned


def _build_result(
    request: SchedulerRequest,
    *,
    allocations: list[MacAllocation],
    debug: dict[str, object],
) -> SchedulerResult:
    """复制请求 envelope，避免 SchedulerResult 与请求失去关联。"""

    return SchedulerResult(
        contract_version=request.contract_version,
        simulation_id=request.simulation_id,
        scheduler_request_id=request.scheduler_request_id,
        tick=request.tick,
        allocations=allocations,
        debug=debug,
    )


# ---------------------------------------------------------------------------
# tr22068 调度算法(独立函数,可切换使用)
# ---------------------------------------------------------------------------

def sortByCQI(queues:dict[str, ChannelState]):
    queues = list(queues.items())
    while(True):
        
        check = queues
        for i in range(len(queues) - 1):
            for j in range(0, len(queues)-i-1):
                if queues[j][1].cqi < queues[j + 1][1].cqi:
                    queues[j], queues[j + 1] = queues[j + 1], queues[j]
        if (check == queues):
            return dict(queues)