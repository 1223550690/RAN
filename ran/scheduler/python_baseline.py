from __future__ import annotations

import math

from ran.contracts import (
    ChannelState,
    MacAllocation,
    RlcQueue,
    SchedulerRequest,
    SchedulerResult,
)
from ran.radio.mcs_tables import cqi_to_mcs
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
            mcs = cqi_to_mcs(cqi)  # standard CQI→MCS mapping (TS 38.214)
            layers = 1 if cqi < 10 else 2
            capacity = estimate_transport_bytes(prbs=prbs, mcs=mcs, layers=layers, slot_ms=request.slot_ms)
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
    """Allocate integers using the largest remainder method, guaranteeing strict conservation of the total PRB count."""

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
    """Copy the request envelope so the SchedulerResult stays associated with the request."""

    return SchedulerResult(
        contract_version=request.contract_version,
        simulation_id=request.simulation_id,
        scheduler_request_id=request.scheduler_request_id,
        tick=request.tick,
        allocations=allocations,
        debug=debug,
    )


# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# tr22068 scheduling algorithms (standalone functions, switchable)
# ---------------------------------------------------------------------------

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
            prbs = math.floor(int(request.total_prbs * ratio))
            cqi = channel.cqi if channel else 1
            mcs = cqi_to_mcs(cqi)  # standard CQI→MCS mapping (TS 38.214)
            layers = 1 if cqi < 10 else 2
            capacity = estimate_transport_bytes(prbs=prbs, mcs=mcs, layers=layers, slot_ms=request.slot_ms)
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
            prbs = math.floor(int(request.total_prbs * ratio))
            cqi = channel.cqi if channel else 1
            mcs = cqi_to_mcs(cqi)  # standard CQI→MCS mapping (TS 38.214)
            layers = 1 if cqi < 10 else 2
            capacity = estimate_transport_bytes(prbs=prbs, mcs=mcs, layers=layers, slot_ms=request.slot_ms)
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

            prbs = math.floor(int(request.total_prbs * ratio))
            cqi = channel.cqi if channel else 1
            mcs = max(1, min(28, int(cqi * 1.8))) 
            layers = 1 if cqi < 10 else 2
            capacity = estimate_transport_bytes(prbs=prbs, mcs=mcs, layers=layers, slot_ms=request.slot_ms)
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
        for i in range(0, length):
            #Weights assigned according to bsr sizes
            weights[active[i].ue_id, active[i].drb_id] = length -i
            weight_sum += length-i
        allocations: list[MacAllocation] = []
        for queue in active:
            
            channel = channel_by_ue[queue.ue_id]
            ratio = weights[(queue.ue_id, queue.drb_id)] / weight_sum if weight_sum else 0.0

            prbs = math.floor(int(request.total_prbs * ratio))
            cqi = channel.cqi if channel else 1
            mcs = cqi_to_mcs(cqi)  # standard CQI→MCS mapping (TS 38.214)
            layers = 1 if cqi < 10 else 2
            capacity = estimate_transport_bytes(prbs=prbs, mcs=mcs, layers=layers, slot_ms=request.slot_ms)
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