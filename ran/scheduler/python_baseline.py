from __future__ import annotations

from ran.contracts import MacAllocation, SchedulerRequest, SchedulerResult
from ran.radio.ofdm import estimate_transport_bytes


class PythonBaselineScheduler:
    """Python fallback scheduler。

    当前用于替代 Java scheduler，确保 MVP 可以正常模拟。
    """

    def allocate(self, request: SchedulerRequest) -> SchedulerResult:
        """根据 RLC queue、CQI 和 slice policy 分配 PRB。

        输入:
        - SchedulerRequest。

        输出:
        - SchedulerResult。
        """

        active = [queue for queue in request.rlc_queues if queue.queued_bytes + queue.retransmission_bytes > 0]
        if not active:
            return SchedulerResult(tick=request.tick, allocations=[], debug={"reason": "no_active_queue"})
        channel_by_ue = {state.ue_id: state for state in request.channel_states}
        policy_by_slice = {policy.slice_id: policy for policy in request.slice_policies}
        weight_sum = 0.0
        weights: dict[tuple[str, int], float] = {}
        for queue in active:
            #channel_by_ue, policy_by_slice, weights, weight_sum, queue = mvbScheduling(channel_by_ue, policy_by_slice, weights, weight_sum, queue)
            
            channel_by_ue, policy_by_slice, weights, weight_sum, queue  = roundRobinScheduling(channel_by_ue, policy_by_slice, weights, weight_sum, queue)
        allocations: list[MacAllocation] = []
        for queue in active:
            channel = channel_by_ue.get(queue.ue_id)
            ratio = weights[(queue.ue_id, queue.drb_id)] / weight_sum if weight_sum else 0.0
            prbs = max(1, int(request.total_prbs * ratio))
            cqi = channel.cqi if channel else 1
            mcs = max(1, min(28, int(cqi * 1.8)))
            layers = 1 if cqi < 10 else 2
            capacity = estimate_transport_bytes(prbs=prbs, mcs=mcs, layers=layers)
            scheduled = min(queue.queued_bytes + queue.retransmission_bytes, capacity)
            allocations.append(
                MacAllocation(
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
        return SchedulerResult(tick=request.tick, allocations=allocations, debug={"implementation": "python_baseline"})

# MVP Minimal Implementation: Weights are roughly determined by queue size, CQI, and slice priority.
def mvbScheduling(channel_by_ue, policy_by_slice, weights, weight_sum, queue):
    channel = channel_by_ue.get(queue.ue_id)
    policy = policy_by_slice.get(queue.slice_id)
    cqi = channel.cqi if channel else 1
    priority = policy.priority if policy else 5

    weight = max(1.0, (queue.queued_bytes + queue.retransmission_bytes) / 1_000_000) * max(1, cqi) / max(1, priority)
    weights[(queue.ue_id, queue.drb_id)] = weight
    weight_sum += weight
    return channel_by_ue, policy_by_slice, weights, weight_sum, queue
    

#Equal transmission to all, guarantees fairness
def roundRobinScheduling(channel_by_ue, policy_by_slice, weights, weight_sum, queue):
    weight = 1
    weights[(queue.ue_id, queue.drb_id)] = weight
    weight_sum += weight
    return channel_by_ue, policy_by_slice, weights, weight_sum, queue

#Highest potential throughput gets most PRBs
def maxThroughputScheduling(channel_by_ue, policy_by_slice, weights, weight_sum, queue):
    
    return channel_by_ue, policy_by_slice, weights, weight_sum, queue 