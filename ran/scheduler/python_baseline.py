from __future__ import annotations

from ran.contracts import MacAllocation, SchedulerRequest, SchedulerResult, RlcQueue
from ran.radio.ofdm import estimate_transport_bytes


class PythonBaselineScheduler:
    """Project implementation detail."""

    def allocate(self, request: SchedulerRequest) -> SchedulerResult:
        """Project implementation detail."""

        active = [queue for queue in request.rlc_queues if queue.queued_bytes + queue.retransmission_bytes > 0]
        if not active:
            return SchedulerResult(tick=request.tick, allocations=[], debug={"reason": "no_active_queue"})
        channel_by_ue = {state.ue_id: state for state in request.channel_states}
        policy_by_slice = {policy.slice_id: policy for policy in request.slice_policies}
        weight_sum = 0.0
        weights: dict[tuple[str, int], float] = {}
        active = sortByBSR(active)
        i = 0
        for queue in active:
            #Initial trial allocations
            weights[queue.ue_id, queue.drb_id] = len(active) -i
            weight_sum += len(active) -i
            i+= 1
            #channel_by_ue, policy_by_slice, weights, weight_sum, queue= mvbScheduling(channel_by_ue, policy_by_slice, weights, weight_sum, queue)
            #channel_by_ue, policy_by_slice, weights, weight_sum, queue = roundRobinScheduling(channel_by_ue, policy_by_slice, weights, weight_sum, queue)
            #channel_by_ue, policy_by_slice, weights, weight_sum, queue  = grantBasedScheduling(channel_by_ue, policy_by_slice, weights, weight_sum, queue)
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
    #UPLINK ALGORITHMS
    #Time management to be implemented later

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
def grantBasedScheduling(channel_by_ue, policy_by_slice, weights, weight_sum, queue):

    
    
    return channel_by_ue, policy_by_slice, weights, weight_sum, queue
def sortByBSR(queues:list[RlcQueue]):
    while(True):
        check = queues
        for i in range(0, len(queues)-1):
            if (queues[i].queued_bytes + queues[i].retransmission_bytes < queues[i+1].queued_bytes + queues[i+1].retransmission_bytes):
                temp = queues[i]
                queues[i] = queues[i+1]
                queues[i+1] = temp
        if (check == queues):
            return queues