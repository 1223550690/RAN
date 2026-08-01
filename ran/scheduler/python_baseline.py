from __future__ import annotations

from ran.contracts import MacAllocation, SchedulerRequest, SchedulerResult, RlcQueue, ChannelState
from ran.radio.ofdm import estimate_transport_bytes


class PythonBaselineScheduler:
    """Project implementation detail."""

    def allocate(self, request: SchedulerRequest) -> SchedulerResult:
        """Project implementation detail."""

        active = [queue for queue in request.rlc_queues if queue.queued_bytes + queue.retransmission_bytes > 0]
        if not active:
            return SchedulerResult(tick=request.tick, allocations=[], debug={"reason": "no_active_queue"})
        channel_by_ue = request.channel_states
        policy_by_slice = {policy.slice_id: policy for policy in request.slice_policies}
        allocations = grantBasedULScheduling(channel_by_ue, request, active)
        print(allocations)
        return SchedulerResult(tick=request.tick, allocations=allocations, debug={"implementation": "python_baseline"})
    #UPLINK ALGORITHMS
    #Time management to be implemented later



#Equal transmission to all, guarantees fairness
def roundRobinDLScheduling(channel_by_ue, request, active):
        weight_sum = 0.0
        weights: dict[tuple[str, int], float] = {}
        for queue in active:
            weights[queue.ue_id, queue.drb_id] = 1
            weight_sum += 1
        allocations: list[MacAllocation] = []
        for queue in active:
            
            channel = channel_by_ue[queue.ue_id]
            ratio = weights[(queue.ue_id, queue.drb_id)] / weight_sum if weight_sum else 0.0
            prbs = max(1, int(request.total_prbs * ratio))
            cqi = channel.cqi if channel else 1
            mcs = max(1, min(28, int(cqi * 1.8))) #Change how mcs works fundamentally
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
        return allocations

#Highest potential throughput gets most PRBs
def maxThroughputDLScheduling(channel_by_ue, request, active):
        
        weights: dict[str, float] = {}
        channel_by_ue = sortByCQI(channel_by_ue)
        for queue in active:
            weights[queue.ue_id] = 0
        channel_by_ue = list(channel_by_ue.items())
        weights[channel_by_ue[0][1].ue_id] = 1
        weight_sum = 1.0
        channel_by_ue = dict(channel_by_ue)
        allocations: list[MacAllocation] = []
        for queue in active:
            
            channel = channel_by_ue[queue.ue_id]
            ratio = weights[queue.ue_id] / weight_sum if weight_sum else 0.0
            prbs = max(1, int(request.total_prbs * ratio))
            cqi = channel.cqi if channel else 1
            mcs = max(1, min(28, int(cqi * 1.8))) #Change how mcs works fundamentally
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
        return allocations

def grantBasedULScheduling(channel_by_ue, request, active):
        weight_sum = 0.0
        weights: dict[tuple[str, int], float] = {}
        for queue in active:
            #Weights assigned according to ratio of bytes
            bytes = queue.queued_bytes + queue.retransmission_bytes
            weights[queue.ue_id, queue.drb_id] = bytes
            weight_sum += bytes
        allocations: list[MacAllocation] = []
        for queue in active:
            
            channel = channel_by_ue[queue.ue_id]
            ratio = weights[(queue.ue_id, queue.drb_id)] / weight_sum if weight_sum else 0.0

            prbs = max(1, int(request.total_prbs * ratio))
            cqi = channel.cqi if channel else 1
            mcs = max(1, min(28, int(cqi * 1.8))) #Change how mcs works fundamentally
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
        return allocations

def weightedULScheduling(channel_by_ue, request, active):
        weight_sum = 0.0
        weights: dict[tuple[str, int], float] = {}
        active = sortByBSR(active)
        length = len(active)
        print(active)
        for i in range(0, length):
            #Weights assigned according to bsr sizes
            weights[active[i].ue_id, active[i].drb_id] = length -i
            weight_sum += length-i
        allocations: list[MacAllocation] = []
        for queue in active:
            
            channel = channel_by_ue[queue.ue_id]
            ratio = weights[(queue.ue_id, queue.drb_id)] / weight_sum if weight_sum else 0.0

            prbs = max(1, int(request.total_prbs * ratio))
            cqi = channel.cqi if channel else 1
            mcs = max(1, min(28, int(cqi * 1.8))) #Change how mcs works fundamentally
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
        return allocations

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